from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTextEdit, QComboBox, QGroupBox, QFormLayout, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont


class ToolWorker(QThread):
    """后台工具执行线程"""
    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, tool_name: str, params: dict):
        super().__init__()
        self.tool_name = tool_name
        self.params = params

    def run(self):
        try:
            # 模拟异步调用，实际项目中应集成 ToolDispatcher
            # 这里为了演示 GUI 逻辑，暂时返回模拟数据或调用简单的同步逻辑
            from sdwan_desktop.tools.registry import tool_registry
            from sdwan_desktop.core.types.tool import ToolRequest
            from sdwan_desktop.core.types.context import FlowContext
            import asyncio
            
            tool_class = tool_registry.get_tool(self.tool_name)
            if not tool_class:
                raise Exception(f"Tool {self.tool_name} not found")
            
            request = ToolRequest(tool_name=self.tool_name, parameters=self.params)
            ctx = FlowContext(flow_id="gui-session", flow_name="gui-tool-execution")
            
            # 在后台线程中运行异步任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                tool_instance = tool_class()
                # 注意：大多数工具目前是异步的，需要 await
                result = loop.run_until_complete(tool_instance.execute(request, ctx))
                self.result_ready.emit(result.to_json_dict())
            finally:
                loop.close()
                
        except Exception as e:
            self.error_occurred.emit(str(e))


class ToolsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_tools()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # 工具选择区
        tool_group = QGroupBox("工具选择")
        tool_layout = QFormLayout()
        
        self.tool_combo = QComboBox()
        self.tool_combo.setMinimumWidth(200)  # 确保下拉框有足够宽度
        self.target_input = QLineEdit()
        self.param_inputs = {} # 动态参数输入框
        
        tool_layout.addRow("选择工具:", self.tool_combo)
        tool_layout.addRow("目标地址:", self.target_input)
        
        tool_group.setLayout(tool_layout)
        layout.addWidget(tool_group)
        
        # 参数配置区 (动态)
        self.param_group = QGroupBox("参数配置")
        self.param_layout = QFormLayout()
        self.param_group.setLayout(self.param_layout)
        layout.addWidget(self.param_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        self.execute_btn = QPushButton("执行")
        self.execute_btn.clicked.connect(self.on_execute)
        btn_layout.addWidget(self.execute_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 结果显示区
        result_label = QLabel("执行结果:")
        layout.addWidget(result_label)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.output_text)
        
        self.setLayout(layout)
        
        # 连接信号
        self.tool_combo.currentTextChanged.connect(self.on_tool_changed)

    def load_tools(self):
        from sdwan_desktop.tools.registry import tool_registry
        tools = tool_registry.list_tools()
        # 过滤出适合在 GUI 快速展示的网络工具
        display_tools = [t for t in tools if t in ["ping", "dns", "tcping", "traceroute"]]
        
        self.tool_combo.clear()  # 清空现有项
        self.tool_combo.addItems(display_tools)
        
        if display_tools:
            self.on_tool_changed(display_tools[0])

    def on_tool_changed(self, tool_name):
        # 清空旧参数输入框
        while self.param_layout.count():
            item = self.param_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.param_inputs.clear()
        
        # 根据工具添加常用参数
        if tool_name == "ping":
            self.add_param_input("count", "发包次数", "4")
            self.add_param_input("timeout", "超时(秒)", "5")
        elif tool_name == "dns":
            self.add_param_input("server", "DNS服务器", "8.8.8.8")
            self.add_param_input("type", "记录类型", "A")
        elif tool_name == "tcping":
            self.add_param_input("port", "端口", "80")
            self.add_param_input("count", "次数", "4")

    def add_param_input(self, key, label, default=""):
        line_edit = QLineEdit(default)
        self.param_layout.addRow(label + ":", line_edit)
        self.param_inputs[key] = line_edit

    def on_execute(self):
        tool_name = self.tool_combo.currentText()
        target = self.target_input.text()
        if not target:
            self.output_text.append("错误: 请输入目标地址\n")
            return
            
        params = {"host": target}
        for key, widget in self.param_inputs.items():
            val = widget.text()
            if val:
                # 尝试转换为数字
                try:
                    if '.' in val:
                        params[key] = float(val)
                    else:
                        params[key] = int(val)
                except ValueError:
                    params[key] = val
        
        self.output_text.append(f"正在执行 {tool_name} {target}...\n")
        self.execute_btn.setEnabled(False)
        
        self.worker = ToolWorker(tool_name, params)
        self.worker.result_ready.connect(self.on_result)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.finished.connect(lambda: self.execute_btn.setEnabled(True))
        self.worker.start()

    def on_result(self, data):
        self.output_text.append(f"\n--- 执行成功 ---\n")
        self.output_text.append(f"耗时: {data.get('duration_ms', 0):.2f} ms\n")
        if data.get('data'):
            for k, v in data['data'].items():
                self.output_text.append(f"{k}: {v}\n")
        else:
            self.output_text.append(str(data))
        self.output_text.append("\n")

    def on_error(self, msg):
        self.output_text.append(f"\n--- 执行失败 ---\n{msg}\n\n")
