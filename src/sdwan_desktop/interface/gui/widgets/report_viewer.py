from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel, QProgressBar
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, QThread, Signal
import os


class ReportLoader(QThread):
    """后台报告加载线程"""
    finished = Signal(str)  # HTML 内容

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.finished.emit(content)
        except Exception as e:
            self.finished.emit(f"<h1>加载失败</h1><p>{str(e)}</p>")


class ReportViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.loader = None

    def init_ui(self):
        layout = QVBoxLayout()
        
        # 按钮区
        btn_layout = QHBoxLayout()
        self.open_btn = QPushButton("打开本地报告")
        self.open_btn.clicked.connect(self.on_open_report)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 浏览器预览区
        self.browser = QWebEngineView()
        self.browser.setHtml("<h1>SD-WAN 诊断报告预览</h1><p>请点击“打开本地报告”加载 HTML 文件。</p>")
        
        # 性能优化：禁用部分不必要的 WebEngine 功能以提升大文件渲染速度
        settings = self.browser.settings()
        settings.setAttribute(settings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        
        layout.addWidget(self.browser)
        
        self.setLayout(layout)

    def on_open_report(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "打开报告", "", "HTML Files (*.html);;All Files (*)")
        if file_path:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # 启动后台加载线程
            self.loader = ReportLoader(file_path)
            self.loader.finished.connect(self.on_report_loaded)
            self.loader.start()

    def on_report_loaded(self, html_content):
        """报告加载完成后的处理"""
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        self.browser.setHtml(html_content)
