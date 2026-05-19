"""深度诊断 GUI：默认经 agentctl 子进程执行 ``deep-dive``（与终端 CLI 同宿主）。"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import ValidationError
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sdwan_desktop.interface.gui.agentctl_worker import AgentctlWorker
from sdwan_desktop.interface.gui.deep_dive_launch import deep_dive_use_inprocess
from sdwan_desktop.interface.gui.deep_dive_worker import DeepDiveWorker
from sdwan_desktop.interface.gui.flow_run_params import DeepDiveGuiRunParams
from sdwan_desktop.interface.gui.path_display import display_default_yaml_path
from sdwan_desktop.interface.gui.tab_form_layout import (
    add_diagnosis_group,
    compact_form_field,
    diagnosis_tab_layout,
    finalize_diagnosis_form,
    set_compact_status,
)
from sdwan_desktop.interface.gui.report_flow import (
    GuiReportActions,
    deliver_gui_report,
    open_report_folder,
    preview_report,
    prompt_save_report,
    set_report_actions_enabled,
    wire_report_action_labels,
)
from sdwan_desktop.services.collector.cpe_credentials_loader import (
    default_cpe_credentials_path,
    load_device_credentials_file,
)
from sdwan_desktop.services.collector.cpe_view_credentials_loader import (
    default_cpe_view_credentials_path,
)

if TYPE_CHECKING:
    from sdwan_desktop.interface.gui.main_window import MainWindow

logger = logging.getLogger(__name__)


class DeepDiveTab(QWidget):
    """深度诊断：默认子进程 ``agentctl deep-dive``；``SDWAN_DEEP_DIVE_INPROCESS=1`` 时进程内 Flow。"""

    diagnosis_started = Signal(object)

    def __init__(
        self,
        credentials_file: Optional[Path] = None,
        view_credentials_file: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._main: Optional[MainWindow] = None
        self._credentials_path = (
            Path(credentials_file) if credentials_file is not None else default_cpe_credentials_path()
        )
        self._view_credentials_path = (
            Path(view_credentials_file)
            if view_credentials_file is not None
            else default_cpe_view_credentials_path()
        )
        self._worker: Optional[object] = None
        self._last_out: Optional[Path] = None
        self._init_ui()

    def attach_main_window(self, window: MainWindow) -> None:
        self._main = window
        wire_report_action_labels(window, self._report_actions())

    def _init_ui(self) -> None:
        root, form, self.status_label = diagnosis_tab_layout(
            self,
            (
                "深度诊断：CPE 配置/运行态专检 + 拓扑；默认对 baidu / youtube / tiktok "
                "做 PC 侧 DNS(A)+TCP+traceroute「链路分流」探测（与 CLI deep-dive 默认一致，"
                "不含 DNS 系统对照即「DNS 分流」）。"
            ),
        )

        g_cpe = QGroupBox("CPE 连接（必填）")
        f_cpe = QFormLayout()
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("CPE 管理 IP")
        compact_form_field(self.host_input)
        f_cpe.addRow("主机地址", self.host_input)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(23)
        compact_form_field(self.port_spin)
        f_cpe.addRow("端口", self.port_spin)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("登录用户名")
        compact_form_field(self.username_input)
        f_cpe.addRow("用户名", self.username_input)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("可选；亦可使用凭证文件")
        compact_form_field(self.password_input)
        f_cpe.addRow("密码", self.password_input)
        self.protocol = QComboBox()
        self.protocol.addItems(["telnet", "ssh"])
        compact_form_field(self.protocol)
        f_cpe.addRow("协议", self.protocol)
        self.key_file = QLineEdit()
        self.key_file.setPlaceholderText("可选：SSH 私钥（--key-file）")
        compact_form_field(self.key_file)
        key_btn = QPushButton("浏览…")
        key_btn.clicked.connect(self._pick_key)
        row_key = QHBoxLayout()
        row_key.addWidget(self.key_file)
        row_key.addWidget(key_btn)
        w_key = QWidget()
        w_key.setLayout(row_key)
        f_cpe.addRow("SSH 私钥", w_key)
        g_cpe.setLayout(f_cpe)
        add_diagnosis_group(form, g_cpe)

        g_cred = QGroupBox("凭证文件（可选）")
        f_cred = QFormLayout()
        self.cred_file = QLineEdit()
        compact_form_field(self.cred_file)
        cred_display = display_default_yaml_path(
            self._credentials_path, "configs/cpe_credentials.yaml"
        )
        if cred_display:
            self.cred_file.setText(cred_display)
        self.cred_file.setPlaceholderText("configs/cpe_credentials.yaml")
        cred_btn = QPushButton("浏览…")
        cred_btn.clicked.connect(self._pick_cred)
        row_cred = QHBoxLayout()
        row_cred.addWidget(self.cred_file)
        row_cred.addWidget(cred_btn)
        w_cred = QWidget()
        w_cred.setLayout(row_cred)
        f_cred.addRow("设备凭证", w_cred)
        self.view_cred_file = QLineEdit()
        compact_form_field(self.view_cred_file)
        view_display = display_default_yaml_path(
            self._view_credentials_path, "configs/cpe_view_credentials.yaml"
        )
        if view_display:
            self.view_cred_file.setText(view_display)
        self.view_cred_file.setPlaceholderText("configs/cpe_view_credentials.yaml")
        view_btn = QPushButton("浏览…")
        view_btn.clicked.connect(self._pick_view_cred)
        row_view = QHBoxLayout()
        row_view.addWidget(self.view_cred_file)
        row_view.addWidget(view_btn)
        w_view = QWidget()
        w_view.setLayout(row_view)
        f_cred.addRow("视图口令", w_view)
        g_cred.setLayout(f_cred)
        add_diagnosis_group(form, g_cred)
        finalize_diagnosis_form(form)

        row = QHBoxLayout()
        self.start_btn = QPushButton("开始深度诊断")
        self.start_btn.clicked.connect(self.on_start_diagnosis)
        self.preview_btn = QPushButton("在报告预览中打开")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._on_preview)
        self.open_dir_btn = QPushButton("打开报告所在文件夹")
        self.open_dir_btn.setEnabled(False)
        self.open_dir_btn.clicked.connect(self._on_open_dir)
        self.save_as_btn = QPushButton("另存报告")
        self.save_as_btn.setEnabled(False)
        self.save_as_btn.clicked.connect(self._on_save_as)
        row.addWidget(self.start_btn)
        row.addWidget(self.preview_btn)
        row.addWidget(self.open_dir_btn)
        row.addWidget(self.save_as_btn)
        row.addStretch()
        root.addLayout(row)
        root.addWidget(self.status_label)

    def _report_actions(self) -> GuiReportActions:
        return GuiReportActions(
            preview=self.preview_btn,
            open_folder=self.open_dir_btn,
            save_as=self.save_as_btn,
        )

    def _pick_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 SSH 私钥", "", "All (*)")
        if path:
            self.key_file.setText(path)

    def _pick_cred(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择凭证 YAML", "", "YAML (*.yaml *.yml);;All (*)")
        if path:
            self.cred_file.setText(path)

    def _pick_view_cred(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择视图口令 YAML", "", "YAML (*.yaml *.yml);;All (*)")
        if path:
            self.view_cred_file.setText(path)

    def _build_params(self, out: Path) -> DeepDiveGuiRunParams:
        host = self.host_input.text().strip()
        user = self.username_input.text().strip()
        cred_path = self.cred_file.text().strip()
        return DeepDiveGuiRunParams(
            cpe_host=host,
            username=user,
            cpe_port=self.port_spin.value(),
            password=self.password_input.text().strip() or None,
            key_file=self.key_file.text().strip() or None,
            protocol=self.protocol.currentText(),  # type: ignore[arg-type]
            output_path=str(out),
            credentials_file=cred_path or None,
            view_credentials_file=self.view_cred_file.text().strip() or None,
        )

    def _cpe_auth_error(self, host: str) -> Optional[str]:
        """深度诊断必须连 CPE：在启动前校验 SSH 口令/私钥，避免长时间无反馈挂起。"""
        protocol = self.protocol.currentText().strip().lower()
        typed_pw = self.password_input.text().strip()
        key_path = self.key_file.text().strip()
        cred_path = self.cred_file.text().strip()
        file_pw = ""
        if cred_path and host:
            file_pw = (
                load_device_credentials_file(Path(cred_path), host).get("password") or ""
            )
        has_login = bool(typed_pw or file_pw or key_path)
        if protocol == "ssh" and not has_login:
            return "SSH 连接需要填写密码、私钥，或在凭证 YAML 中为该主机配置 password。"
        if protocol == "telnet" and not has_login:
            return (
                "未配置 Telnet 登录密码（界面或凭证文件）。"
                "连接可能长时间无响应；请填写密码或检查 configs/cpe_credentials.yaml。"
            )
        return None

    def _ensure_main_window(self) -> None:
        if self._main is not None:
            return
        from sdwan_desktop.interface.gui.main_window import MainWindow

        win = self.window()
        if isinstance(win, MainWindow):
            self.attach_main_window(win)

    def _on_progress(self, percent: int, text: str) -> None:
        if text:
            set_compact_status(self.status_label, text)

    def on_start_diagnosis(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        host = self.host_input.text().strip()
        user = self.username_input.text().strip()
        if not host or not user:
            QMessageBox.warning(self, "深度诊断", "请填写 CPE 主机地址与用户名。")
            return
        auth_err = self._cpe_auth_error(host)
        if auth_err:
            QMessageBox.warning(self, "深度诊断", auth_err)
            return

        tf = tempfile.NamedTemporaryFile(suffix=".html", prefix="deep_dive_", delete=False)
        tf.close()
        out_path = Path(tf.name)

        try:
            self._ensure_main_window()
            params = self._build_params(out_path)
        except ValidationError as exc:
            QMessageBox.warning(self, "深度诊断", str(exc))
            return
        except Exception as exc:
            logger.exception("深度诊断参数准备失败")
            QMessageBox.critical(self, "深度诊断", str(exc))
            return

        self.start_btn.setEnabled(False)
        set_report_actions_enabled(self._report_actions(), None, main=self._main)
        if deep_dive_use_inprocess():
            set_compact_status(
                self.status_label,
                "正在启动深度诊断（进程内，CPE 采集可能需数分钟）…",
            )
            logger.info("deep-dive GUI in-process: cpe=%s", params.cpe_host)
            worker: object = DeepDiveWorker(params, out_path)
        else:
            set_compact_status(
                self.status_label,
                "正在启动深度诊断（与 CLI 相同子进程）…",
            )
            argv = params.to_argv()
            logger.info("deep-dive GUI subprocess: cpe=%s argv=%s", params.cpe_host, argv[:8])
            worker = AgentctlWorker(argv, out_path)

        self._worker = worker
        self.diagnosis_started.emit(worker)
        worker.progress_updated.connect(self._on_progress)  # type: ignore[attr-defined]
        worker.finished_ok.connect(self._on_done)  # type: ignore[attr-defined]
        worker.finished_err.connect(self._on_err)  # type: ignore[attr-defined]
        worker.finished.connect(self._on_worker_finished)  # type: ignore[attr-defined]
        worker.start()  # type: ignore[attr-defined]

    def _on_worker_finished(self) -> None:
        self.start_btn.setEnabled(True)
        if self._main:
            self._main.end_diagnosis(self._worker)

    def _on_done(self, path: object) -> None:
        p = Path(path)
        self._last_out = deliver_gui_report(
            self._main,
            p,
            status_setter=lambda t: set_compact_status(self.status_label, t),
            actions=self._report_actions(),
            parent=self,
            auto_open=True,
            prompt_save_on_complete=False,
            defer_auto_open=True,
        )

    def _on_err(self, msg: str) -> None:
        brief = msg.split("\n", 1)[0].strip()
        if "原因:" in msg:
            for part in msg.replace("\n", "；").split("；"):
                if part.strip().startswith("原因:"):
                    brief = part.strip()
                    break
        set_compact_status(self.status_label, f"失败：{brief[:120]}")
        QMessageBox.critical(self, "深度诊断", msg[:2000])

    def _on_preview(self) -> None:
        if self._last_out:
            preview_report(self._main, self._last_out, parent=self, switch_tab=True)

    def _on_open_dir(self) -> None:
        if self._last_out:
            open_report_folder(self._last_out)

    def _on_save_as(self) -> None:
        if self._last_out:
            self._last_out = prompt_save_report(self._last_out, self)
            set_report_actions_enabled(self._report_actions(), self._last_out, main=self._main)
            set_compact_status(self.status_label, f"已保存: {self._last_out}")
