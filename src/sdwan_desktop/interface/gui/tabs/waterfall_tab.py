from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QTextEdit, QProgressBar, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QThread
import os

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity


class WaterfallWorker(QThread):
    """业务监测后台工作线程"""
    progress_updated = Signal(int, str)
    monitoring_completed = Signal(object)
    monitoring_failed = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            self.progress_updated.emit(10, "正在启动浏览器...")
            import time
            time.sleep(1)
            
            self.progress_updated.emit(40, f"正在访问 {self.url} ...")
            time.sleep(2)
            
            self.progress_updated.emit(80, "正在分析性能指标...")
            time.sleep(1)
            
            self.progress_updated.emit(100, "监测完成")
            
            result = DiagnosisResult(
                diagnosis_type="waterfall",
                target_description=self.url,
                summary="页面加载分析完成",
                severity=Severity.INFO
            )
            # 模拟一些性能建议
            from sdwan_desktop.core.types.diagnosis import Recommendation
            result.recommendations.append(Recommendation(
                action="优化图片资源",
                priority=2,
                expected_outcome="减少首屏加载时间约 0.5s"
            ))
            
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
        self.start_btn = QPushButton("开始监测")
        self.start_btn.clicked.connect(self.on_start_monitoring)
        
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
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
        
        self.worker = WaterfallWorker(url)
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
