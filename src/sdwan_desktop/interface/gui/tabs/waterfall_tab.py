"""业务监测 GUI：HAR 采集 + 与 CLI 一致的 Waterfall HTML 报告。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity
from sdwan_desktop.interface.gui.report_flow import (
    GuiReportActions,
    deliver_gui_report,
    open_report_folder,
    preview_report,
    prompt_save_report,
    set_report_actions_enabled,
    wire_report_action_labels,
)

if TYPE_CHECKING:
    from sdwan_desktop.interface.gui.main_window import MainWindow


class WaterfallWorker(QThread):
    """业务监测后台线程：HAR → 解析 → 规则 → HTML 报告（与 CLI waterfall 对齐）。"""

    progress_updated = Signal(int, str)
    monitoring_completed = Signal(object, object)  # DiagnosisResult, Path
    monitoring_failed = Signal(str)

    def __init__(
        self,
        url: str,
        headless: bool = True,
        report_path: Optional[Path] = None,
        proxy: Optional[str] = None,
    ):
        super().__init__()
        self.url = url
        self.headless = headless
        self.report_path = report_path
        self.proxy = (proxy or "").strip() or None

    def run(self) -> None:
        try:
            import asyncio

            from sdwan_desktop.tools.bootstrap import ensure_har_tool_registered

            ensure_har_tool_registered()
            from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
            from sdwan_desktop.services.parser.har_parser import HarParser
            from sdwan_desktop.services.analyzer.rules.performance import (
                check_page_load_time,
                check_dns_performance,
                check_tcp_connect_performance,
                check_ssl_handshake_performance,
                check_ttfb_performance,
                check_download_performance,
                check_render_blocking,
            )
            from sdwan_desktop.services.reporter.report_generator import ReportGenerator
            from sdwan_desktop.core.types.tool import ToolRequest
            from sdwan_desktop.core.types.context import FlowContext

            self.progress_updated.emit(10, "正在启动浏览器…")
            har_tool = HarCaptureTool()
            params: dict = {
                "url": self.url,
                "headless": self.headless,
                "timeout": 90000,
                # 与 HarCaptureTool 新默认一致：``load`` 命中后内部仍会再尝试 networkidle/固定等待；
                # 直接 networkidle 在常驻轮询的门户站点上会整体超时。
                "wait_until": "load",
            }
            if self.proxy:
                params["proxy"] = self.proxy
            request = ToolRequest(
                tool_name="har_capture",
                parameters=params,
            )
            ctx = FlowContext(flow_id="gui-waterfall", flow_name="gui-waterfall-monitoring")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                har_result = loop.run_until_complete(har_tool.execute(request, ctx))
            finally:
                loop.close()

            if not har_result or not har_result.success:
                error_msg = har_result.error_message if har_result else "未知错误"
                raise RuntimeError(f"HAR 采集失败: {error_msg}")

            har_path = har_result.data.get("har_file_path") if har_result.data else None
            if not har_path or not os.path.exists(har_path):
                raise RuntimeError(f"HAR 文件不存在: {har_path}")

            self.progress_updated.emit(40, f"HAR 已保存: {os.path.basename(har_path)}")

            self.progress_updated.emit(55, "正在解析 HAR…")
            waterfall_result = HarParser().parse(har_path, target_url=self.url)
            self.progress_updated.emit(
                70,
                f"解析完成: {waterfall_result.total_requests} 个资源",
            )

            self.progress_updated.emit(80, "正在分析性能指标…")
            all_issues: list = []
            all_issues.extend(check_page_load_time(waterfall_result))
            all_issues.extend(check_dns_performance(waterfall_result))
            all_issues.extend(check_tcp_connect_performance(waterfall_result))
            all_issues.extend(check_ssl_handshake_performance(waterfall_result))
            all_issues.extend(check_ttfb_performance(waterfall_result))
            all_issues.extend(check_download_performance(waterfall_result))
            all_issues.extend(check_render_blocking(waterfall_result))

            out = self.report_path
            if out is None:
                tf = tempfile.NamedTemporaryFile(
                    suffix=".html", prefix="waterfall_", delete=False
                )
                tf.close()
                out = Path(tf.name)

            self.progress_updated.emit(90, "正在生成 HTML 报告…")
            ReportGenerator().generate_waterfall_report(
                waterfall_result, all_issues, str(out)
            )

            result = DiagnosisResult(
                diagnosis_type="waterfall",
                target_description=self.url,
                summary=(
                    f"页面加载 {waterfall_result.page_load_time:.0f} ms，"
                    f"{waterfall_result.total_requests} 个资源，"
                    f"{len(all_issues)} 条性能提示"
                ),
                severity=Severity.WARNING if all_issues else Severity.INFO,
                root_causes=[],
                recommendations=[],
            )

            from sdwan_desktop.core.types.diagnosis import DiagnosisEvidence, Recommendation

            for issue in all_issues:
                result.recommendations.append(
                    Recommendation(
                        action=issue.get("message", "未知问题"),
                        priority=issue.get("severity", 2),
                        expected_outcome=issue.get("suggestion", "优化性能"),
                    )
                )

            result.evidences.append(
                DiagnosisEvidence(
                    step_name="waterfall_analysis",
                    description=result.summary,
                    probe_results=[],
                    config_snapshots={
                        "waterfall_result": waterfall_result,
                        "performance_issues": all_issues,
                        "har_file_path": har_path,
                    },
                )
            )

            self.progress_updated.emit(100, "监测完成")
            self.monitoring_completed.emit(result, out)

        except Exception as exc:
            self.monitoring_failed.emit(str(exc))


class WaterfallTab(QWidget):
    diagnosis_started = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._main: Optional[MainWindow] = None
        self._last_report: Optional[Path] = None
        self._worker: Optional[WaterfallWorker] = None
        self._init_ui()

    def attach_main_window(self, window: MainWindow) -> None:
        self._main = window
        wire_report_action_labels(window, self._report_actions())

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("目标 URL:"))
        self.url_input = QLineEdit("https://www.example.com")
        self.headless_checkbox = QCheckBox("无头模式 (Headless)")
        self.headless_checkbox.setChecked(True)
        self.start_btn = QPushButton("开始监测")
        self.start_btn.clicked.connect(self.on_start_monitoring)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.headless_checkbox)
        url_layout.addWidget(self.start_btn)
        layout.addLayout(url_layout)

        # 代理输入：留空时按 HTTPS_PROXY/HTTP_PROXY 环境变量回退；适用于内网/出网受限场景。
        proxy_layout = QHBoxLayout()
        proxy_layout.addWidget(QLabel("HTTP 代理 (可选):"))
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText(
            "如 http://127.0.0.1:7890；留空时按 HTTPS_PROXY/HTTP_PROXY 环境变量回退"
        )
        proxy_layout.addWidget(self.proxy_input)
        layout.addLayout(proxy_layout)

        self.progress_bar = QProgressBar()
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

        layout.addWidget(QLabel("监测摘要:"))
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        btn_layout = QHBoxLayout()
        self.preview_btn = QPushButton("在报告预览中打开")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._on_preview)
        self.open_folder_btn = QPushButton("打开报告所在文件夹")
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._on_open_folder)
        self.save_btn = QPushButton("另存报告")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save_as)
        btn_layout.addStretch()
        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _report_actions(self) -> GuiReportActions:
        return GuiReportActions(
            preview=self.preview_btn,
            open_folder=self.open_folder_btn,
            save_as=self.save_btn,
        )

    def on_start_monitoring(self) -> None:
        url = self.url_input.text().strip()
        if not url.startswith(("http://", "https://")):
            self.status_label.setText("错误: URL 必须以 http:// 或 https:// 开头")
            return

        if self._worker and self._worker.isRunning():
            return

        self.start_btn.setEnabled(False)
        set_report_actions_enabled(self._report_actions(), None, main=self._main)
        self.output_text.clear()
        self.progress_bar.setValue(0)

        self._worker = WaterfallWorker(
            url,
            headless=self.headless_checkbox.isChecked(),
            proxy=self.proxy_input.text(),
        )
        self.diagnosis_started.emit(self._worker)
        self._worker.progress_updated.connect(self.on_progress)
        self._worker.monitoring_completed.connect(self.on_completed)
        self._worker.monitoring_failed.connect(self.on_failed)
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
        if not isinstance(result, DiagnosisResult):
            self.on_failed("结果类型异常")
            return
        rp = Path(report_path)

        lines = [
            "=== 业务监测报告 ===",
            "",
            f"目标地址: {result.target_description}",
            f"整体状态: {result.severity.value.upper()}",
            f"HTML 报告: {rp}",
            "",
        ]
        if result.recommendations:
            lines.append("--- 优化建议 ---")
            for i, rec in enumerate(result.recommendations, 1):
                lines.append(f"{i}. [{rec.priority}] {rec.action}")
                lines.append(f"   预期效果: {rec.expected_outcome}")
                lines.append("")
        else:
            lines.append("未发现明显的性能瓶颈。")

        self.output_text.setText("\n".join(lines))

        self._last_report = deliver_gui_report(
            self._main,
            rp,
            status_setter=lambda t: self.status_label.setText(f"{result.summary}\n{t}"),
            actions=self._report_actions(),
            parent=self,
            auto_open=True,
            prompt_save_on_complete=True,
        )

    def on_failed(self, msg: str) -> None:
        self.status_label.setText(f"监测失败: {msg}")
        self.output_text.append(f"\n错误详情: {msg}\n")

    def _on_preview(self) -> None:
        if self._last_report:
            preview_report(self._main, self._last_report, parent=self, switch_tab=True)

    def _on_open_folder(self) -> None:
        if self._last_report:
            open_report_folder(self._last_report)

    def _on_save_as(self) -> None:
        if self._last_report:
            self._last_report = prompt_save_report(self._last_report, self)
            set_report_actions_enabled(self._report_actions(), self._last_report, main=self._main)
            self.status_label.setText(f"已保存: {self._last_report}")
