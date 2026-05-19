"""业务路径诊断 GUI：封装 CLI 等价参数并生成 HTML/JSON 报告。"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from pydantic import ValidationError
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
from sdwan_desktop.interface.gui.flow_run_params import BusinessDiagnoseGuiRunParams
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
from sdwan_desktop.services.collector.cpe_credentials_loader import default_cpe_credentials_path
from sdwan_desktop.services.collector.cpe_view_credentials_loader import default_cpe_view_credentials_path

if TYPE_CHECKING:
    from sdwan_desktop.interface.gui.main_window import MainWindow

logger = logging.getLogger(__name__)


class BusinessDiagnoseTab(QWidget):
    """业务路径诊断：与 CLI ``business-diagnose`` 对齐。"""

    diagnosis_started = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._main: Optional[MainWindow] = None
        self._worker: Optional[AgentctlWorker] = None
        self._last_out: Optional[Path] = None
        self._init_ui()

    def attach_main_window(self, window: MainWindow) -> None:
        self._main = window
        wire_report_action_labels(window, self._report_actions())

    def _init_ui(self) -> None:
        root, form, self.status = diagnosis_tab_layout(
            self,
            "业务路径诊断：对单个 FQDN:端口做 DNS+TCP+可选 traceroute；可选连接 CPE 联合分析。",
        )

        g1 = QGroupBox("业务目标（每次仅一个，格式 FQDN:端口）")
        f1 = QFormLayout(g1)
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("例如 www.example.com:443")
        compact_form_field(self.target_input)
        f1.addRow("FQDN:端口", self.target_input)
        add_diagnosis_group(form, g1)

        g2 = QGroupBox("选项")
        f2 = QFormLayout()
        self.output_format = QComboBox()
        self.output_format.addItems(["html", "json"])
        compact_form_field(self.output_format)
        f2.addRow("输出格式 (-F)", self.output_format)
        self.biz_dns = QLineEdit()
        self.biz_dns.setPlaceholderText("可选：业务 DNS IPv4（等价 -S）")
        compact_form_field(self.biz_dns)
        f2.addRow("业务 DNS", self.biz_dns)
        self.collect_pc = QCheckBox("采集本机快照（默认开启；对应未传 --no-collect-pc）")
        self.collect_pc.setChecked(True)
        f2.addRow("", self.collect_pc)
        self.allow_probe_only = QCheckBox("探测失败时仅本机报告（--allow-probe-only，不推荐）")
        f2.addRow("", self.allow_probe_only)
        self.no_traceroute = QCheckBox("跳过本机路由追踪（--no-traceroute）")
        f2.addRow("", self.no_traceroute)
        g2.setLayout(f2)
        add_diagnosis_group(form, g2)

        g3 = QGroupBox("可选：CPE 联合（与 CLI 一致：主机 + 用户名必填）")
        f3 = QFormLayout()
        self.cpe_host = QLineEdit()
        self.cpe_host.setPlaceholderText("CPE 管理 IP")
        compact_form_field(self.cpe_host)
        f3.addRow("CPE 地址", self.cpe_host)
        self.cpe_port = QSpinBox()
        self.cpe_port.setRange(1, 65535)
        self.cpe_port.setValue(23)
        compact_form_field(self.cpe_port)
        f3.addRow("端口", self.cpe_port)
        self.cpe_user = QLineEdit()
        self.cpe_user.setPlaceholderText("登录用户名")
        compact_form_field(self.cpe_user)
        f3.addRow("用户名", self.cpe_user)
        self.cpe_password = QLineEdit()
        self.cpe_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.cpe_password.setPlaceholderText("可选；亦可使用凭证文件")
        compact_form_field(self.cpe_password)
        f3.addRow("密码", self.cpe_password)
        self.protocol = QComboBox()
        self.protocol.addItems(["telnet", "ssh"])
        compact_form_field(self.protocol)
        f3.addRow("协议", self.protocol)
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
        f3.addRow("SSH 私钥", w_key)
        self.cred_file = QLineEdit()
        compact_form_field(self.cred_file)
        default_cred_display = display_default_yaml_path(
            default_cpe_credentials_path(), "configs/cpe_credentials.yaml"
        )
        if default_cred_display:
            self.cred_file.setText(default_cred_display)
        self.cred_file.setPlaceholderText("configs/cpe_credentials.yaml")
        cred_btn = QPushButton("浏览…")
        cred_btn.clicked.connect(self._pick_cred)
        row_cred = QHBoxLayout()
        row_cred.addWidget(self.cred_file)
        row_cred.addWidget(cred_btn)
        w_cred = QWidget()
        w_cred.setLayout(row_cred)
        f3.addRow("设备凭证 YAML", w_cred)
        self.view_cred_file = QLineEdit()
        compact_form_field(self.view_cred_file)
        default_view_display = display_default_yaml_path(
            default_cpe_view_credentials_path(), "configs/cpe_view_credentials.yaml"
        )
        if default_view_display:
            self.view_cred_file.setText(default_view_display)
        self.view_cred_file.setPlaceholderText("configs/cpe_view_credentials.yaml")
        view_btn = QPushButton("浏览…")
        view_btn.clicked.connect(self._pick_view_cred)
        row_view = QHBoxLayout()
        row_view.addWidget(self.view_cred_file)
        row_view.addWidget(view_btn)
        w_view = QWidget()
        w_view.setLayout(row_view)
        f3.addRow("视图口令 YAML", w_view)
        g3.setLayout(f3)
        add_diagnosis_group(form, g3)
        finalize_diagnosis_form(form)

        row = QHBoxLayout()
        self.run_btn = QPushButton("开始诊断")
        self.run_btn.clicked.connect(self._on_run)
        self.preview_btn = QPushButton("在报告预览中打开")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._on_preview)
        self.open_btn = QPushButton("打开报告所在文件夹")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._on_open_dir)
        self.save_as_btn = QPushButton("另存报告")
        self.save_as_btn.setEnabled(False)
        self.save_as_btn.clicked.connect(self._on_save_as)
        row.addWidget(self.run_btn)
        row.addWidget(self.preview_btn)
        row.addWidget(self.open_btn)
        row.addWidget(self.save_as_btn)
        row.addStretch()
        root.addLayout(row)
        root.addWidget(self.status)

    def _report_actions(self) -> GuiReportActions:
        return GuiReportActions(
            preview=self.preview_btn,
            open_folder=self.open_btn,
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

    def _parse_single_target(self) -> str:
        raw = self.target_input.text().strip()
        if not raw:
            return ""
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(lines) > 1:
            raise ValueError("业务路径诊断每次仅支持一个目标（FQDN:端口），请勿输入多行。")
        return lines[0]

    def _build_params(self, out: Path) -> BusinessDiagnoseGuiRunParams:
        fmt = self.output_format.currentText()
        target = self._parse_single_target()
        return BusinessDiagnoseGuiRunParams(
            biz_targets=(target,),
            output_path=str(out),
            output_format=fmt,  # type: ignore[arg-type]
            biz_dns_server=self.biz_dns.text().strip() or None,
            collect_pc=self.collect_pc.isChecked(),
            allow_probe_only=self.allow_probe_only.isChecked(),
            no_traceroute=self.no_traceroute.isChecked(),
            cpe_host=self.cpe_host.text().strip() or None,
            cpe_port=self.cpe_port.value(),
            username=self.cpe_user.text().strip() or None,
            password=self.cpe_password.text().strip() or None,
            key_file=self.key_file.text().strip() or None,
            protocol=self.protocol.currentText(),  # type: ignore[arg-type]
            credentials_file=self.cred_file.text().strip() or None,
            view_credentials_file=self.view_cred_file.text().strip() or None,
        )

    def _on_run(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        try:
            target = self._parse_single_target()
        except ValueError as exc:
            QMessageBox.warning(self, "业务路径诊断", str(exc))
            return
        if not target:
            QMessageBox.warning(self, "业务路径诊断", "请输入业务目标（FQDN:端口）。")
            return

        suffix = ".json" if self.output_format.currentText() == "json" else ".html"
        tf = tempfile.NamedTemporaryFile(
            suffix=suffix, prefix="business_diagnose_", delete=False
        )
        tf.close()
        out_path = Path(tf.name)

        try:
            params = self._build_params(out_path)
            argv = params.to_argv()
        except (ValidationError, ValueError) as exc:
            QMessageBox.warning(self, "业务路径诊断", str(exc))
            return

        self.run_btn.setEnabled(False)
        set_report_actions_enabled(self._report_actions(), None, main=self._main)
        set_compact_status(self.status, "正在运行 business-diagnose …")
        logger.info("business-diagnose GUI argv: %s", argv[:12])

        self._worker = AgentctlWorker(argv, out_path)
        self.diagnosis_started.emit(self._worker)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.finished_err.connect(self._on_err)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self) -> None:
        self.run_btn.setEnabled(True)
        if self._main:
            self._main.end_diagnosis()

    def _on_done(self, path: object) -> None:
        p = Path(path)
        self._last_out = deliver_gui_report(
            self._main,
            p,
            status_setter=lambda t: set_compact_status(self.status, t),
            actions=self._report_actions(),
            parent=self,
            auto_open=True,
            prompt_save_on_complete=True,
        )

    def _on_err(self, msg: str) -> None:
        brief = msg.split("\n", 1)[0].strip()
        if "原因:" in msg:
            for part in msg.replace("\n", "；").split("；"):
                if part.strip().startswith("原因:"):
                    brief = part.strip()
                    break
        set_compact_status(self.status, f"失败：{brief[:120]}")
        QMessageBox.critical(self, "业务路径诊断", msg[:2000])

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
            set_compact_status(self.status, f"已保存: {self._last_out}")
