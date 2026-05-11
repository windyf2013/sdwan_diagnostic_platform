from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QTextEdit, QProgressBar, QFileDialog, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QThread
import os

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity


class WaterfallWorker(QThread):
    """业务监测后台工作线程 - 使用真实的 HAR 采集和解析"""
    progress_updated = Signal(int, str)
    monitoring_completed = Signal(object)
    monitoring_failed = Signal(str)

    def __init__(self, url: str, headless: bool = True):
        super().__init__()
        self.url = url
        self.headless = headless

    def run(self):
        try:
            import asyncio
            from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
            from sdwan_desktop.services.parser.har_parser import HarParser
            from sdwan_desktop.services.analyzer.perf_analyzer import PerfAnalyzer
            from sdwan_desktop.services.analyzer.rules.performance import (
                check_page_load_time,
                check_dns_performance,
                check_tcp_connect_performance,
                check_ssl_handshake_performance,
                check_ttfb_performance,
                check_download_performance,
                check_render_blocking,
            )
            
            # 1. HAR 采集
            self.progress_updated.emit(10, "正在启动浏览器...")
            har_tool = HarCaptureTool()
            
            # 构造 ToolRequest
            from sdwan_desktop.core.types.tool import ToolRequest
            from sdwan_desktop.core.types.context import FlowContext
            
            request = ToolRequest(
                tool_name="har_capture",
                parameters={
                    "url": self.url,
                    "headless": self.headless,
                    "timeout": 60000,
                    "wait_until": "networkidle"
                }
            )
            ctx = FlowContext(flow_id="gui-waterfall", flow_name="gui-waterfall-monitoring")
            
            # 在后台线程中运行异步任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                har_result = loop.run_until_complete(har_tool.execute(request, ctx))
            finally:
                loop.close()
            
            # 检查执行结果
            if not har_result or not har_result.success:
                error_msg = har_result.error_message if har_result else "未知错误"
                raise Exception(f"HAR 采集失败: {error_msg}")
            
            har_path = har_result.data.get("har_file_path") if har_result.data else None
            if not har_path or not os.path.exists(har_path):
                raise Exception(f"HAR 文件不存在: {har_path}")
            
            self.progress_updated.emit(40, f"HAR 文件已保存: {os.path.basename(har_path)}")
            
            # 2. HAR 解析
            self.progress_updated.emit(50, "正在解析 HAR 文件...")
            parser = HarParser()
            waterfall_result = parser.parse(har_path)
            
            self.progress_updated.emit(70, f"解析完成: {waterfall_result.total_requests} 个资源")
            
            # 3. 性能规则匹配
            self.progress_updated.emit(80, "正在分析性能指标...")
            all_issues = []
            all_issues.extend(check_page_load_time(waterfall_result))
            all_issues.extend(check_dns_performance(waterfall_result))
            all_issues.extend(check_tcp_connect_performance(waterfall_result))
            all_issues.extend(check_ssl_handshake_performance(waterfall_result))
            all_issues.extend(check_ttfb_performance(waterfall_result))
            all_issues.extend(check_download_performance(waterfall_result))
            all_issues.extend(check_render_blocking(waterfall_result))
            
            self.progress_updated.emit(90, f"发现 {len(all_issues)} 个性能问题")
            
            # 4. 构造诊断结果
            self.progress_updated.emit(100, "监测完成")
            
            result = DiagnosisResult(
                diagnosis_type="waterfall",
                target_description=self.url,
                summary=f"页面加载分析完成 ({waterfall_result.page_load_time:.0f}ms)",
                severity=Severity.WARNING if all_issues else Severity.INFO,
                root_causes=[],
                recommendations=[]
            )
            
            # 将性能问题转换为建议
            for issue in all_issues:
                from sdwan_desktop.core.types.diagnosis import Recommendation
                result.recommendations.append(Recommendation(
                    action=issue.get("message", "未知问题"),
                    priority=issue.get("severity", 2),
                    expected_outcome=issue.get("suggestion", "优化性能")
                ))
            
            # 附加 waterfall 数据供报告生成使用（通过 evidence 存储）
            from sdwan_desktop.core.types.diagnosis import DiagnosisEvidence
            waterfall_evidence = DiagnosisEvidence(
                step_name="waterfall_analysis",
                description=f"HAR分析结果: {waterfall_result.total_requests}个资源, 总耗时{waterfall_result.page_load_time:.0f}ms",
                probe_results=[],
                config_snapshots={
                    "waterfall_result": waterfall_result,
                    "performance_issues": all_issues,
                    "har_file_path": har_path
                }
            )
            result.evidences.append(waterfall_evidence)
            
            self.monitoring_completed.emit(result)
            
        except Exception as e:
            self.monitoring_failed.emit(str(e))


class WaterfallTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # URL 输入区
        url_layout = QHBoxLayout()
        url_label = QLabel("目标 URL:")
        self.url_input = QLineEdit("https://www.example.com")
        self.headless_checkbox = QCheckBox("无头模式 (Headless)")
        self.headless_checkbox.setChecked(True)
        self.start_btn = QPushButton("开始监测")
        self.start_btn.clicked.connect(self.on_start_monitoring)
        
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.headless_checkbox)
        url_layout.addWidget(self.start_btn)
        layout.addLayout(url_layout)
        
        # 进度区
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        
        # 结果摘要区
        result_label = QLabel("监测摘要:")
        layout.addWidget(result_label)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存报告")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.on_save_report)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def on_start_monitoring(self):
        url = self.url_input.text()
        if not url.startswith(("http://", "https://")):
            self.status_label.setText("错误: URL 必须以 http:// 或 https:// 开头")
            return
            
        self.start_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.output_text.clear()
        self.progress_bar.setValue(0)
        
        headless = self.headless_checkbox.isChecked()
        self.worker = WaterfallWorker(url, headless=headless)
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.monitoring_completed.connect(self.on_completed)
        self.worker.monitoring_failed.connect(self.on_failed)
        self.worker.finished.connect(lambda: self.start_btn.setEnabled(True))
        self.worker.start()

    def on_progress(self, percent, text):
        self.progress_bar.setValue(percent)
        self.status_label.setText(text)

    def on_completed(self, result: DiagnosisResult):
        self.status_label.setText(result.summary)
        self.save_btn.setEnabled(True)
        
        output = f"=== 业务监测报告 ===\n\n"
        output += f"目标地址: {result.target_description}\n"
        output += f"整体状态: {result.severity.value.upper()}\n\n"
        
        if result.recommendations:
            output += "--- 优化建议 ---\n"
            for i, rec in enumerate(result.recommendations, 1):
                output += f"{i}. [{rec.priority}] {rec.action}\n"
                output += f"   预期效果: {rec.expected_outcome}\n\n"
        else:
            output += "未发现明显的性能瓶颈。\n"
            
        self.output_text.setText(output)

    def on_failed(self, msg):
        self.status_label.setText(f"监测失败: {msg}")
        self.output_text.append(f"\n错误详情: {msg}\n")
        self.start_btn.setEnabled(True)

    def on_save_report(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存报告", "", "HTML Files (*.html);;All Files (*)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("<h1>SD-WAN 业务监测报告</h1><pre>")
                f.write(self.output_text.toPlainText())
                f.write("</pre>")
            self.status_label.setText(f"报告已保存至: {os.path.basename(file_path)}")
