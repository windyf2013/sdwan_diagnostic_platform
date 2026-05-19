"""网络工具 GUI：与 tools registry 参数名对齐并展示解析 IP。"""

from __future__ import annotations

import socket
from typing import Any, Dict, Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def _resolve_ipv4(host: str) -> Optional[str]:
    """将域名解析为 IPv4 供结果区展示（失败返回 None）。"""
    host = host.strip()
    if not host:
        return None
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            return str(infos[0][4][0])
    except OSError:
        return None
    return None


class ToolWorker(QThread):
    """后台工具执行线程"""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, tool_name: str, params: dict):
        super().__init__()
        self.tool_name = tool_name
        self.params = params

    def run(self) -> None:
        try:
            import asyncio

            from sdwan_desktop.tools.bootstrap import ensure_core_tools_registered

            ensure_core_tools_registered()
            from sdwan_desktop.tools.registry import tool_registry
            from sdwan_desktop.core.types.tool import ToolRequest
            from sdwan_desktop.core.types.context import FlowContext

            tool_class = tool_registry.get_tool(self.tool_name)
            if not tool_class:
                raise RuntimeError(f"Tool {self.tool_name} not found")

            request = ToolRequest(tool_name=self.tool_name, parameters=self.params)
            ctx = FlowContext(flow_id="gui-session", flow_name="gui-tool-execution")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                tool_instance = tool_class()
                result = loop.run_until_complete(tool_instance.execute(request, ctx))
                self.result_ready.emit(result.to_json_dict())
            finally:
                loop.close()

        except Exception as exc:
            self.error_occurred.emit(str(exc))


class ToolsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._last_target = ""
        self.init_ui()
        self.load_tools()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)

        tool_group = QGroupBox("工具选择")
        tool_layout = QFormLayout()

        self.tool_combo = QComboBox()
        self.tool_combo.setMinimumWidth(200)
        self.target_input = QLineEdit()
        self.target_label = QLabel("目标地址:")
        self.param_inputs: Dict[str, QLineEdit] = {}

        tool_layout.addRow("选择工具:", self.tool_combo)
        tool_layout.addRow(self.target_label, self.target_input)

        tool_group.setLayout(tool_layout)
        layout.addWidget(tool_group)

        self.param_group = QGroupBox("参数配置")
        self.param_layout = QFormLayout()
        self.param_group.setLayout(self.param_layout)
        layout.addWidget(self.param_group)

        btn_layout = QHBoxLayout()
        self.execute_btn = QPushButton("执行")
        self.execute_btn.clicked.connect(self.on_execute)
        btn_layout.addWidget(self.execute_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addWidget(QLabel("执行结果:"))
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.output_text)

        self.setLayout(layout)
        self.tool_combo.currentTextChanged.connect(self.on_tool_changed)

    def load_tools(self) -> None:
        from sdwan_desktop.tools.bootstrap import ensure_core_tools_registered
        from sdwan_desktop.tools.registry import tool_registry

        ensure_core_tools_registered()
        tools = tool_registry.list_tools()
        display_tools = [t for t in tools if t in ["ping", "dns", "tcping", "traceroute"]]

        self.tool_combo.clear()
        self.tool_combo.setEnabled(True)
        self.target_input.setEnabled(True)
        if display_tools:
            self.tool_combo.addItems(display_tools)
            self.on_tool_changed(display_tools[0])
        else:
            self.tool_combo.addItem("（未注册工具）")
            self.tool_combo.setEnabled(False)
            self.output_text.append(
                "未加载到网络工具。请确认安装完整，或从源码启动 GUI。\n"
            )

    def on_tool_changed(self, tool_name: str) -> None:
        while self.param_layout.count():
            item = self.param_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.param_inputs.clear()

        if tool_name == "dns":
            self.target_label.setText("域名:")
            self.target_input.setPlaceholderText("例如 www.example.com")
            self.add_param_input("dns_server", "DNS服务器", "8.8.8.8")
            self.add_param_input("record_type", "记录类型", "A")
        elif tool_name == "tcping":
            self.target_label.setText("目标地址:")
            self.target_input.setPlaceholderText("IP 或域名")
            self.add_param_input("port", "端口", "80")
            self.add_param_input("count", "次数", "4")
        elif tool_name == "ping":
            self.target_label.setText("目标地址:")
            self.target_input.setPlaceholderText("IP 或域名")
            self.add_param_input("count", "发包次数", "4")
            self.add_param_input("timeout", "超时(秒)", "5")
        elif tool_name == "traceroute":
            self.target_label.setText("目标地址:")
            self.target_input.setPlaceholderText("IP 或域名")
            self.add_param_input("max_hops", "最大跳数", "30")
        else:
            self.target_label.setText("目标地址:")
            self.target_input.setPlaceholderText("")

    def add_param_input(self, key: str, label: str, default: str = "") -> None:
        line_edit = QLineEdit(default)
        self.param_layout.addRow(label + ":", line_edit)
        self.param_inputs[key] = line_edit

    def _build_tool_params(self, tool_name: str, target: str) -> Dict[str, Any]:
        """按工具 schema 组装参数（DNS 使用 domain，其余使用 host）。"""
        if tool_name == "dns":
            params: Dict[str, Any] = {"domain": target}
        else:
            params = {"host": target}
        for key, widget in self.param_inputs.items():
            val = widget.text().strip()
            if not val:
                continue
            try:
                if "." in val and key not in ("type", "server"):
                    params[key] = float(val)
                else:
                    params[key] = int(val)
            except ValueError:
                params[key] = val
        if tool_name == "dns" and "record_type" in params:
            params["record_type"] = str(params["record_type"]).upper()
        return params

    def on_execute(self) -> None:
        tool_name = self.tool_combo.currentText()
        if not tool_name or tool_name.startswith("（"):
            self.output_text.append("错误: 无可用工具，请重启应用或检查安装。\n")
            return
        target = self.target_input.text().strip()
        if not target:
            self.output_text.append("错误: 请输入目标\n")
            return

        self._last_target = target
        params = self._build_tool_params(tool_name, target)

        self.output_text.append(f"正在执行 {tool_name} {target}...\n")
        self.execute_btn.setEnabled(False)

        self.worker = ToolWorker(tool_name, params)
        self.worker.result_ready.connect(self.on_result)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.finished.connect(lambda: self.execute_btn.setEnabled(True))
        self.worker.start()

    def on_result(self, data: dict) -> None:
        self.output_text.append(f"\n{'='*60}\n")
        self.output_text.append("✅ 执行成功\n")
        self.output_text.append(f"{'='*60}\n")

        if "duration_ms" in data:
            self.output_text.append(f"⏱️  耗时: {data['duration_ms']:.2f} ms\n")

        tool_name = self.tool_combo.currentText()
        result_data = data.get("data") or {}

        if tool_name == "ping":
            self._format_ping_result(result_data, self._last_target)
        elif tool_name == "dns":
            self._format_dns_result(result_data)
        elif tool_name == "tcping":
            self._format_tcping_result(result_data)
        elif tool_name == "traceroute":
            self._format_traceroute_result(result_data, self._last_target)
        elif result_data:
            for k, v in result_data.items():
                self.output_text.append(f"📌 {k}: {v}\n")
        else:
            self.output_text.append(str(data))

        self.output_text.append(f"\n{'='*60}\n\n")

    def _format_ping_result(self, data: dict, target_host: str) -> None:
        if target_host:
            self.output_text.append(f"🎯 目标: {target_host}\n")
        resolved = _resolve_ipv4(target_host)
        if resolved:
            self.output_text.append(f"📍 解析 IP: {resolved}\n")
        if data.get("packets_sent") is not None:
            self.output_text.append(f"📤 发送: {data['packets_sent']} 个数据包\n")
        if data.get("packets_received") is not None:
            self.output_text.append(f"📥 接收: {data['packets_received']} 个数据包\n")
        if data.get("loss_rate") is not None:
            self.output_text.append(f"📊 丢包率: {data['loss_rate'] * 100:.1f}%\n")
        if data.get("rtt_avg") is not None:
            self.output_text.append(f"⚡ 平均 RTT: {data['rtt_avg']:.2f} ms\n")
        if data.get("rtt_min") is not None:
            self.output_text.append(f"⚡ 最小 RTT: {data['rtt_min']:.2f} ms\n")
        if data.get("rtt_max") is not None:
            self.output_text.append(f"⚡ 最大 RTT: {data['rtt_max']:.2f} ms\n")
        if data.get("ttl") is not None:
            self.output_text.append(f"🔢 TTL: {data['ttl']}\n")

    def _format_dns_result(self, data: dict) -> None:
        if data.get("domain"):
            self.output_text.append(f"🌐 域名: {data['domain']}\n")
        server = data.get("server") or data.get("dns_server_used")
        if server:
            self.output_text.append(f"🔍 DNS 服务器: {server}\n")
        rtype = data.get("query_type") or data.get("record_type")
        if rtype:
            self.output_text.append(f"📋 记录类型: {rtype}\n")
        ips = data.get("resolved_ips") or []
        if ips:
            self.output_text.append("✅ 解析 IP:\n")
            for ip in ips:
                self.output_text.append(f"   • {ip}\n")
        elif data.get("success"):
            self.output_text.append("（查询成功，无 A/AAAA 记录返回）\n")
        rt = data.get("response_time_ms") or data.get("rtt_avg")
        if rt is not None:
            self.output_text.append(f"⚡ 响应时间: {float(rt):.2f} ms\n")

    def _format_tcping_result(self, data: dict) -> None:
        if data.get("host"):
            self.output_text.append(f"🎯 目标: {data['host']}\n")
        if data.get("resolved_ip"):
            self.output_text.append(f"📍 解析 IP: {data['resolved_ip']}\n")
        if data.get("port") is not None:
            self.output_text.append(f"🔌 端口: {data['port']}\n")
        if "port_open" in data:
            status = "✅ 可达" if data["port_open"] else "❌ 不可达"
            self.output_text.append(f"📡 状态: {status}\n")
        avg = data.get("response_time_avg")
        if avg is not None:
            self.output_text.append(f"⚡ 平均 RTT: {avg:.2f} ms\n")
        if data.get("loss_rate") is not None:
            self.output_text.append(f"📊 丢包率: {data['loss_rate'] * 100:.1f}%\n")

    def _format_traceroute_result(self, data: dict, target_host: str) -> None:
        if target_host:
            self.output_text.append(f"🎯 目标: {target_host}\n")
        if data.get("target_ip"):
            self.output_text.append(f"📍 目标 IP: {data['target_ip']}\n")
        elif target_host:
            resolved = _resolve_ipv4(target_host)
            if resolved:
                self.output_text.append(f"📍 目标 IP: {resolved}\n")
        hops = data.get("hops") or []
        if hops:
            self.output_text.append(f"\n🛣️  路由路径 ({len(hops)} 跳):\n")
            self.output_text.append(f"{'跳':<6} {'IP 地址':<22} {'RTT (ms)':<20}\n")
            self.output_text.append(f"{'-'*52}\n")
            for hop in hops:
                hop_num = hop.get("hop", hop.get("hop_number", "?"))
                ip = hop.get("ip") or "*"
                rtts = hop.get("rtts") or []
                rtt_str = ", ".join(f"{r:.2f}" for r in rtts) if rtts else "*"
                self.output_text.append(f"{hop_num!s:<6} {ip:<22} {rtt_str:<20}\n")
        if data.get("total_hops") is not None:
            self.output_text.append(f"\n📊 总跳数: {data['total_hops']}\n")
        if data.get("target_reached") is not None:
            reached = "是" if data["target_reached"] else "否"
            self.output_text.append(f"✔ 到达目标: {reached}\n")

    def on_error(self, msg: str) -> None:
        self.output_text.append(f"\n{'='*60}\n")
        self.output_text.append("❌ 执行失败\n")
        self.output_text.append(f"{'='*60}\n")
        self.output_text.append(f"{msg}\n\n")
