"""一键体检 GUI：进程内 FlowRuntime + 共享 quick_check 步骤工厂。"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import ValidationError
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity
from sdwan_desktop.core.types.quick_check_run_config import QuickCheckRunConfig
from sdwan_desktop.interface.gui.report_flow import (
    GuiReportActions,
    deliver_gui_report,
    preview_report,
    set_report_actions_enabled,
    wire_report_action_labels,
    open_report_folder,
)

if TYPE_CHECKING:
    from sdwan_desktop.interface.gui.main_window import MainWindow

logger = logging.getLogger(__name__)


class QuickCheckWorker(QThread):
    """一键体检后台工作线程（与 CLI 共用 handler 工厂）。"""

    progress_updated = Signal(int, str)
    diagnosis_completed = Signal(object, object)  # DiagnosisResult, Optional[Path]
    diagnosis_failed = Signal(str)

    def __init__(self, cfg: QuickCheckRunConfig):
        super().__init__()
        self._cfg = cfg
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    async def _run_async(self) -> None:
        from sdwan_desktop.tools.bootstrap import ensure_core_tools_registered

        ensure_core_tools_registered()
        from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
        from sdwan_desktop.flow.handlers.quick_check_steps import (
            QuickCheckHandlerDeps,
            QuickCheckHandlersParams,
            build_quick_check_step_handlers,
        )
        from sdwan_desktop.runtime.engine import FlowRuntime
        from sdwan_desktop.core.types.context import FlowContext
        from sdwan_desktop.services.analyzer.rule_engine import RuleEngine
        from sdwan_desktop.services.analyzer.rules import (
            CONNECTIVITY_RULES,
            DNS_RULES,
            GATEWAY_RULES,
            SYSTEM_RULES,
        )
        from sdwan_desktop.services.collector.windows_collector import WindowsCollector
        from sdwan_desktop.services.connectivity import ConnectivityTester
        from sdwan_desktop.services.dns_split import DnsSplitTester
        from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder

        trace_id = str(uuid.uuid4())
        ctx = FlowContext(trace_id=trace_id)
        ctx.set("output_format", self._cfg.output_format)

        collector = WindowsCollector()
        connectivity_tester = ConnectivityTester()
        dns_split_tester = DnsSplitTester()
        rule_engine = RuleEngine()
        rule_engine.register_rules(GATEWAY_RULES)
        rule_engine.register_rules(DNS_RULES)
        rule_engine.register_rules(SYSTEM_RULES)
        rule_engine.register_rules(CONNECTIVITY_RULES)
        report_builder = HtmlReportBuilder()

        report_out = Path(self._cfg.report_output) if self._cfg.report_output else None

        handlers = build_quick_check_step_handlers(
            QuickCheckHandlerDeps(
                collector=collector,
                connectivity_tester=connectivity_tester,
                dns_split_tester=dns_split_tester,
                rule_engine=rule_engine,
                report_builder=report_builder,
            ),
            QuickCheckHandlersParams(
                report_output=report_out,
                output_format=self._cfg.output_format,
                progress=lambda pct, msg: self.progress_updated.emit(pct, msg),
                cancelled=lambda: self._is_cancelled,
                console=False,
            ),
        )

        runtime = FlowRuntime()
        await runtime.execute_flow(QUICK_CHECK_FLOW, ctx, handlers)

        diagnosis_result = ctx.get("diagnosis_result")
        if not diagnosis_result:
            self.diagnosis_failed.emit("诊断流程未生成结果")
            return

        report_path: Optional[Path] = None
        raw_path = ctx.get("report_path")
        if raw_path:
            report_path = Path(raw_path)
        elif report_out and report_out.is_file():
            report_path = report_out

        self.diagnosis_completed.emit(diagnosis_result, report_path)

    def run(self) -> None:
        try:
            asyncio.run(self._run_async())
        except Exception as exc:
            if not self._is_cancelled:
                self.diagnosis_failed.emit(str(exc))


class QuickCheckTab(QWidget):
    diagnosis_started = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._main: Optional[MainWindow] = None
        self.current_result: Optional[DiagnosisResult] = None
        self._last_report: Optional[Path] = None
        self._worker: Optional[QuickCheckWorker] = None
        self._init_ui()

    def attach_main_window(self, window: MainWindow) -> None:
        self._main = window
        wire_report_action_labels(window, self._report_actions())

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        info_label = QLabel("一键体检将自动检查您的网络配置、网关连通性及 DNS 解析情况。")
        layout.addWidget(info_label)
        scope = QLabel(
            "范围说明（L1 本机）：不包含 CPE 隧道/策略专检。若需核查某业务域名与端口，请使用「业务路径诊断」；"
            "若需连接 CPE 做运维专检，请使用「深度诊断」。报告含「报告定位与范围」扉页（HTML）。"
        )
        scope.setWordWrap(True)
        layout.addWidget(scope)

        opt = QGroupBox("选项")
        fopt = QFormLayout()
        self.output_format = QComboBox()
        self.output_format.addItems(["html", "json"])
        fopt.addRow("输出格式", self.output_format)
        opt.setLayout(fopt)
        layout.addWidget(opt)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始体检")
        self.start_btn.clicked.connect(self.on_start_check)
        self.preview_btn = QPushButton("在报告预览中打开")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._on_preview)
        self.open_folder_btn = QPushButton("打开报告所在文件夹")
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._on_open_folder)
        self.save_as_btn = QPushButton("另存报告")
        self.save_as_btn.setEnabled(False)
        self.save_as_btn.clicked.connect(self._on_save_as)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addWidget(self.save_as_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

        from PySide6.QtWidgets import QProgressBar

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["检测项", "状态", "详情"])
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.result_table)

        self.setLayout(layout)

    def _report_actions(self) -> GuiReportActions:
        return GuiReportActions(
            preview=self.preview_btn,
            open_folder=self.open_folder_btn,
            save_as=self.save_as_btn,
        )

    def on_start_check(self) -> None:
        if self._worker and self._worker.isRunning():
            return

        fmt = self.output_format.currentText()
        suffix = ".json" if fmt == "json" else ".html"
        tf = tempfile.NamedTemporaryFile(suffix=suffix, prefix="quick_check_", delete=False)
        tf.close()
        out_path = Path(tf.name)

        try:
            cfg = QuickCheckRunConfig(output_format=fmt, report_output=str(out_path))  # type: ignore[arg-type]
        except ValidationError as exc:
            self.status_label.setText(f"参数无效: {exc}")
            return

        self.start_btn.setEnabled(False)
        set_report_actions_enabled(self._report_actions(), None, main=self._main)
        self.result_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self._last_report = None

        self._worker = QuickCheckWorker(cfg)
        self.diagnosis_started.emit(self._worker)
        self._worker.progress_updated.connect(self.on_progress)
        self._worker.diagnosis_completed.connect(self.on_completed)
        self._worker.diagnosis_failed.connect(self.on_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self) -> None:
        self.start_btn.setEnabled(True)
        if self._main:
            self._main.end_diagnosis()

    def on_progress(self, percent: int, text: str) -> None:
        self.progress_bar.setValue(percent)
        self.status_label.setText(text)

    def on_completed(self, result: object, report_path: object) -> None:
        diagnosis = result
        if not isinstance(diagnosis, DiagnosisResult):
            self.on_failed("诊断结果类型异常")
            return

        self.current_result = diagnosis
        rp: Optional[Path] = Path(report_path) if report_path else None

        self.result_table.setRowCount(len(diagnosis.root_causes) if diagnosis.root_causes else 1)
        if not diagnosis.root_causes:
            item_status = QTableWidgetItem("正常")
            item_status.setForeground(Qt.GlobalColor.green)
            self.result_table.setItem(0, 1, item_status)
            self.result_table.setItem(0, 0, QTableWidgetItem("基础配置"))
            self.result_table.setItem(0, 2, QTableWidgetItem("未发现明显异常"))
        else:
            for i, cause in enumerate(diagnosis.root_causes):
                self.result_table.setItem(i, 0, QTableWidgetItem(cause.title))
                status_item = QTableWidgetItem(cause.severity.value.upper())
                if cause.severity == Severity.CRITICAL:
                    color = Qt.GlobalColor.red
                elif cause.severity == Severity.WARNING:
                    color = Qt.GlobalColor.darkYellow
                else:
                    color = Qt.GlobalColor.black
                status_item.setForeground(color)
                self.result_table.setItem(i, 1, status_item)
                self.result_table.setItem(i, 2, QTableWidgetItem(cause.description))

        if rp is not None:
            self._last_report = deliver_gui_report(
                self._main,
                rp,
                status_setter=lambda t: self.status_label.setText(
                    f"体检完成 - {diagnosis.summary}\n{t}"
                ),
                actions=self._report_actions(),
                parent=self,
                auto_open=True,
                prompt_save_on_complete=True,
            )
        else:
            self._last_report = None
            self.status_label.setText(f"体检完成 - {diagnosis.summary}（未生成报告文件）")

    def on_failed(self, msg: str) -> None:
        self.status_label.setText(f"体检失败: {msg}")

    def _on_preview(self) -> None:
        if self._last_report:
            preview_report(self._main, self._last_report, parent=self, switch_tab=True)

    def _on_open_folder(self) -> None:
        if self._last_report:
            open_report_folder(self._last_report)

    def _on_save_as(self) -> None:
        if self._last_report:
            from sdwan_desktop.interface.gui.report_flow import prompt_save_report

            self._last_report = prompt_save_report(self._last_report, self)
            set_report_actions_enabled(self._report_actions(), self._last_report, main=self._main)
            self.status_label.setText(f"已保存: {self._last_report}")
