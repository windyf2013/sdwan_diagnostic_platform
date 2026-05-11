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
        """Display tool execution results with enhanced formatting"""
        self.output_text.append(f"\n{'='*60}\n")
        self.output_text.append(f"✅ 执行成功\n")
        self.output_text.append(f"{'='*60}\n")
        
        # Display basic metrics
        if 'duration_ms' in data:
            self.output_text.append(f"⏱️  耗时: {data['duration_ms']:.2f} ms\n")
        
        # Display detailed data based on tool type
        if data.get('data'):
            tool_name = self.tool_combo.currentText()
            result_data = data['data']
            
            if tool_name == "ping":
                self._format_ping_result(result_data)
            elif tool_name == "dns":
                self._format_dns_result(result_data)
            elif tool_name == "tcping":
                self._format_tcping_result(result_data)
            elif tool_name == "traceroute":
                self._format_traceroute_result(result_data)
            else:
                # Generic display for other tools
                for k, v in result_data.items():
                    self.output_text.append(f"📌 {k}: {v}\n")
        else:
            self.output_text.append(str(data))
        
        self.output_text.append(f"\n{'='*60}\n\n")

    def _format_ping_result(self, data):
        """Format ping test results"""
        if 'target' in data:
            self.output_text.append(f"🎯 目标: {data['target']}\n")
        if 'packets_sent' in data:
            self.output_text.append(f"📤 发送: {data['packets_sent']} 个数据包\n")
        if 'packets_received' in data:
            self.output_text.append(f"📥 接收: {data['packets_received']} 个数据包\n")
        if 'loss_rate' in data:
            loss_pct = data['loss_rate'] * 100
            self.output_text.append(f"📊 丢包率: {loss_pct:.1f}%\n")
        if 'rtt_avg' in data and data['rtt_avg'] is not None:
            self.output_text.append(f"⚡ 平均RTT: {data['rtt_avg']:.2f} ms\n")
        if 'rtt_min' in data and data['rtt_min'] is not None:
            self.output_text.append(f"⚡ 最小RTT: {data['rtt_min']:.2f} ms\n")
        if 'rtt_max' in data and data['rtt_max'] is not None:
            self.output_text.append(f"⚡ 最大RTT: {data['rtt_max']:.2f} ms\n")

    def _format_dns_result(self, data):
        """Format DNS query results"""
        if 'domain' in data:
            self.output_text.append(f"🌐 域名: {data['domain']}\n")
        if 'server' in data:
            self.output_text.append(f"🔍 DNS服务器: {data['server']}\n")
        if 'query_type' in data:
            self.output_text.append(f"📋 查询类型: {data['query_type']}\n")
        if 'resolved_ips' in data and data['resolved_ips']:
            self.output_text.append(f"✅ 解析结果:\n")
            for ip in data['resolved_ips']:
                self.output_text.append(f"   • {ip}\n")
        if 'rtt_avg' in data and data['rtt_avg'] is not None:
            self.output_text.append(f"⚡ 响应时间: {data['rtt_avg']:.2f} ms\n")

    def _format_tcping_result(self, data):
        """Format TCP port test results"""
        if 'target' in data:
            self.output_text.append(f"🎯 目标: {data['target']}\n")
        if 'port' in data:
            self.output_text.append(f"🔌 端口: {data['port']}\n")
        if 'success' in data:
            status = "✅ 可达" if data['success'] else "❌ 不可达"
            self.output_text.append(f"📡 状态: {status}\n")
        if 'rtt_avg' in data and data['rtt_avg'] is not None:
            self.output_text.append(f"⚡ 平均RTT: {data['rtt_avg']:.2f} ms\n")

    def _format_traceroute_result(self, data):
        """Format traceroute results with hop-by-hop details"""
        if 'target' in data:
            self.output_text.append(f"🎯 目标: {data['target']}\n")
        if 'hops' in data and data['hops']:
            self.output_text.append(f"\n🛣️  路由路径 ({len(data['hops'])} 跳):\n")
            self.output_text.append(f"{'序号':<6} {'IP地址':<20} {'RTT (ms)':<25}\n")
            self.output_text.append(f"{'-'*60}\n")
            
            for hop in data['hops']:
                hop_num = hop.get('hop_number', '?')
                ips = hop.get('ip_addresses', [])
                rtts = hop.get('rtts', [])
                
                ip_str = ', '.join(ips) if ips else '*'
                rtt_str = ', '.join([f"{r:.2f}" for r in rtts]) if rtts else '*'
                
                self.output_text.append(f"{hop_num:<6} {ip_str:<20} {rtt_str:<25}\n")
        
        if 'total_hops' in data:
            self.output_text.append(f"\n📊 总跳数: {data['total_hops']}\n")

    def on_error(self, msg):
        self.output_text.append(f"\n{'='*60}\n")
        self.output_text.append(f"❌ 执行失败\n")
        self.output_text.append(f"{'='*60}\n")
        self.output_text.append(f"{msg}\n\n")
