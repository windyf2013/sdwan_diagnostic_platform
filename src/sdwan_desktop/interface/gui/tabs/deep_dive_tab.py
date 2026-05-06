from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QTextEdit, QGroupBox, QFormLayout, QProgressBar, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QThread
import os

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity


class DeepDiveWorker(QThread):
    """深度诊断后台工作线程"""
    progress_updated = Signal(int, str)
    diagnosis_completed = Signal(object)
    diagnosis_failed = Signal(str)

    def __init__(self, cpe_config: dict):
        super().__init__()
        self.cpe_config = cpe_config

    def run(self):
        try:
            self.progress_updated.emit(10, "正在连接 CPE 设备...")
            import time
            time.sleep(1)
            
            self.progress_updated.emit(40, "正在采集配置与拓扑信息...")
            time.sleep(1)
            
            self.progress_updated.emit(70, "正在进行根因分析...")
            time.sleep(1)
            
            self.progress_updated.emit(100, "深度诊断完成")
            
            result = DiagnosisResult(
                diagnosis_type="deep_dive",
                summary=f"CPE {self.cpe_config.get('host', 'Unknown')} 诊断完成",
                severity=Severity.INFO
            )
            # 模拟一个根因
            from sdwan_desktop.core.types.diagnosis import RootCause
            result.root_causes.append(RootCause(
                cause_id="CPE-001",
                title="CPE 隧道状态正常",
                description="所有 Overlay 隧道均处于 Up 状态。",
                severity=Severity.INFO,
                confidence=0.95
            ))
            
            self.diagnosis_completed.emit(result)
        except Exception as e:
            self.diagnosis_failed.emit(str(e))


class DeepDiveTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # CPE 配置区域
        config_group = QGroupBox("CPE 连接配置")
        form_layout = QFormLayout()
        
        self.host_input = QLineEdit("192.168.1.1")
        self.port_input = QLineEdit("22")
        self.username_input = QLineEdit("admin")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        
        form_layout.addRow("主机地址:", self.host_input)
        form_layout.addRow("端口:", self.port_input)
        form_layout.addRow("用户名:", self.username_input)
        form_layout.addRow("密码:", self.password_input)
        
        config_group.setLayout(form_layout)
        layout.addWidget(config_group)
        
        # 按钮区
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始深度诊断")
        self.start_btn.clicked.connect(self.on_start_diagnosis)
        self.save_btn = QPushButton("保存报告")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.on_save_report)
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)
        
        # 进度区
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        
        # 结果输出区
        result_label = QLabel("诊断详情:")
        layout.addWidget(result_label)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)
        
        self.setLayout(layout)

    def on_start_diagnosis(self):
        self.start_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.output_text.clear()
        self.progress_bar.setValue(0)
        
        cpe_config = {
            "host": self.host_input.text(),
            "port": int(self.port_input.text()),
            "username": self.username_input.text(),
            "password": self.password_input.text()
        }
        
        self.worker = DeepDiveWorker(cpe_config)
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.diagnosis_completed.connect(self.on_completed)
        self.worker.diagnosis_failed.connect(self.on_failed)
        self.worker.finished.connect(lambda: self.start_btn.setEnabled(True))
        self.worker.start()

    def on_progress(self, percent, text):
        self.progress_bar.setValue(percent)
        self.status_label.setText(text)

    def on_completed(self, result: DiagnosisResult):
        self.status_label.setText(result.summary)
        self.save_btn.setEnabled(True)
        
        output = f"=== 深度诊断报告 ===\n\n"
        output += f"整体严重程度: {result.severity.value.upper()}\n"
        output += f"置信度: {result.overall_confidence:.2f}\n\n"
        
        if result.root_causes:
            output += "--- 根因分析 ---\n"
            for i, cause in enumerate(result.root_causes, 1):
                output += f"{i}. [{cause.severity.value.upper()}] {cause.title}\n"
                output += f"   描述: {cause.description}\n"
                output += f"   置信度: {cause.confidence:.0%}\n\n"
        else:
            output += "未发现明显根因。\n"
            
        self.output_text.setText(output)

    def on_failed(self, msg):
        self.status_label.setText(f"诊断失败: {msg}")
        self.output_text.append(f"\n错误详情: {msg}\n")
        self.start_btn.setEnabled(True)

    def on_save_report(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存报告", "", "HTML Files (*.html);;All Files (*)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("<h1>SD-WAN 深度诊断报告</h1><pre>")
                f.write(self.output_text.toPlainText())
                f.write("</pre>")
            self.status_label.setText(f"报告已保存至: {os.path.basename(file_path)}")
