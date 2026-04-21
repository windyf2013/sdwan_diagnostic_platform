"""SSH适配器 - 远程设备连接"""

import asyncio
import paramiko
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import socket
import time

from ....core.types.context import Context
from ....tools.registry.decorator import tool_function
from ....tools.registry.dispatcher import ToolRequest


@dataclass
class SshConnection:
    """SSH连接信息"""
    host: str
    port: int
    username: str
    password: Optional[str] = None
    private_key: Optional[str] = None
    timeout: int = 30


@dataclass
class SshCommandResult:
    """SSH命令执行结果"""
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    success: bool


@dataclass
class DeviceInfo:
    """设备信息"""
    vendor: str
    model: str
    version: str
    hostname: str
    serial_number: str = ""
    uptime: str = ""


@tool_function(
    name="ssh_adapter",
    description="SSH远程设备连接",
    timeout=120,
    retry_count=2
)
class SshAdapter:
    """SSH适配器 - 远程设备连接"""
    
    def __init__(self):
        self._connections: Dict[str, paramiko.SSHClient] = {}
        self._connection_info: Dict[str, SshConnection] = {}
    
    async def execute(self, request: ToolRequest, ctx: Context) -> Dict[str, Any]:
        """执行SSH操作"""
        action = request.params.get("action", "connect")
        
        if action == "connect":
            return await self._connect(request.params)
        elif action == "execute":
            return await self._execute_command(request.params)
        elif action == "disconnect":
            return await self._disconnect(request.params)
        elif action == "collect_config":
            return await self._collect_configuration(request.params)
        else:
            return {
                "status": "error",
                "data": None,
                "error": f"未知操作: {action}"
            }
    
    async def _connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """建立SSH连接"""
        host = params.get("host", "")
        port = params.get("port", 22)
        username = params.get("username", "")
        password = params.get("password", "")
        private_key = params.get("private_key", "")
        timeout = params.get("timeout", 30)
        
        if not host or not username:
            return {
                "status": "error",
                "data": None,
                "error": "必须提供主机地址和用户名"
            }
        
        connection_id = f"{host}:{port}:{username}"
        
        # 检查是否已连接
        if connection_id in self._connections:
            return {
                "status": "success",
                "data": {
                    "connection_id": connection_id,
                    "message": "已存在连接"
                },
                "error": None
            }
        
        try:
            # 创建SSH客户端
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接参数
            connect_params = {
                "hostname": host,
                "port": port,
                "username": username,
                "timeout": timeout
            }
            
            if password:
                connect_params["password"] = password
            elif private_key:
                # 加载私钥
                import io
                key_file = io.StringIO(private_key)
                pkey = paramiko.RSAKey.from_private_key(key_file)
                connect_params["pkey"] = pkey
            
            # 建立连接
            await asyncio.get_event_loop().run_in_executor(
                None, client.connect, **connect_params
            )
            
            # 保存连接
            self._connections[connection_id] = client
            self._connection_info[connection_id] = SshConnection(
                host=host,
                port=port,
                username=username,
                password=password,
                private_key=private_key,
                timeout=timeout
            )
            
            # 获取设备信息
            device_info = await self._get_device_info(client)
            
            return {
                "status": "success",
                "data": {
                    "connection_id": connection_id,
                    "device_info": device_info,
                    "message": "连接成功"
                },
                "error": None
            }
            
        except paramiko.AuthenticationException as e:
            return {
                "status": "error",
                "data": None,
                "error": f"认证失败: {str(e)}"
            }
        except paramiko.SSHException as e:
            return {
                "status": "error",
                "data": None,
                "error": f"SSH错误: {str(e)}"
            }
        except socket.timeout as e:
            return {
                "status": "error",
                "data": None,
                "error": f"连接超时: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "error": f"连接失败: {str(e)}"
            }
    
    async def _execute_command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行SSH命令"""
        connection_id = params.get("connection_id", "")
        command = params.get("command", "")
        timeout = params.get("timeout", 30)
        
        if not connection_id or not command:
            return {
                "status": "error",
                "data": None,
                "error": "必须提供连接ID和命令"
            }
        
        if connection_id not in self._connections:
            return {
                "status": "error",
                "data": None,
                "error": f"连接不存在: {connection_id}"
            }
        
        client = self._connections[connection_id]
        
        try:
            start_time = time.time()
            
            # 执行命令
            stdin, stdout, stderr = await asyncio.get_event_loop().run_in_executor(
                None, client.exec_command, command, timeout
            )
            
            # 读取输出
            stdout_str = await asyncio.get_event_loop().run_in_executor(
                None, stdout.read
            ).decode("utf-8", errors="ignore")
            
            stderr_str = await asyncio.get_event_loop().run_in_executor(
                None, stderr.read
            ).decode("utf-8", errors="ignore")
            
            # 获取退出码
            exit_code = stdout.channel.recv_exit_status()
            
            duration_ms = (time.time() - start_time) * 1000
            
            result = SshCommandResult(
                command=command,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=exit_code,
                duration_ms=duration_ms,
                success=exit_code == 0
            )
            
            return {
                "status": "success",
                "data": {
                    "result": {
                        "command": result.command,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.exit_code,
                        "duration_ms": result.duration_ms,
                        "success": result.success
                    }
                },
                "error": None
            }
            
        except socket.timeout as e:
            return {
                "status": "error",
                "data": None,
                "error": f"命令执行超时: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "error": f"命令执行失败: {str(e)}"
            }
    
    async def _disconnect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """断开SSH连接"""
        connection_id = params.get("connection_id", "")
        
        if not connection_id:
            return {
                "status": "error",
                "data": None,
                "error": "必须提供连接ID"
            }
        
        if connection_id not in self._connections:
            return {
                "status": "error",
                "data": None,
                "error": f"连接不存在: {connection_id}"
            }
        
        try:
            client = self._connections[connection_id]
            client.close()
            
            # 移除连接
            del self._connections[connection_id]
            if connection_id in self._connection_info:
                del self._connection_info[connection_id]
            
            return {
                "status": "success",
                "data": {
                    "message": "连接已断开"
                },
                "error": None
            }
            
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "error": f"断开连接失败: {str(e)}"
            }
    
    async def _collect_configuration(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """收集设备配置"""
        connection_id = params.get("connection_id", "")
        device_type = params.get("device_type", "auto")
        
        if not connection_id:
            return {
                "status": "error",
                "data": None,
                "error": "必须提供连接ID"
            }
        
        if connection_id not in self._connections:
            return {
                "status": "error",
                "data": None,
                "error": f"连接不存在: {connection_id}"
            }
        
        client = self._connections[connection_id]
        
        try:
            # 自动检测设备类型
            if device_type == "auto":
                device_type = await self._detect_device_type(client)
            
            # 根据设备类型执行相应的收集命令
            if device_type == "cisco_sdwan":
                config = await self._collect_cisco_sdwan_config(client)
            elif device_type == "huawei":
                config = await self._collect_huawei_config(client)
            elif device_type == "fortinet":
                config = await self._collect_fortinet_config(client)
            else:
                config = await self._collect_generic_config(client)
            
            return {
                "status": "success",
                "data": {
                    "device_type": device_type,
                    "configuration": config
                },
                "error": None
            }
            
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "error": f"配置收集失败: {str(e)}"
            }
    
    async def _get_device_info(self, client: paramiko.SSHClient) -> DeviceInfo:
        """获取设备信息"""
        try:
            # 执行show version或类似命令
            stdin, stdout, stderr = client.exec_command("show version", timeout=10)
            output = stdout.read().decode("utf-8", errors="ignore")
            
            # 解析输出
            vendor = "unknown"
            model = "unknown"
            version = "unknown"
            hostname = "unknown"
            
            # 尝试检测厂商
            output_lower = output.lower()
            
            if "cisco" in output_lower:
                vendor = "cisco"
                # 解析Cisco版本信息
                import re
                version_match = re.search(r"Version\s+(\S+)", output)
                if version_match:
                    version = version_match.group(1)
                
                model_match = re.search(r"(c\d+|vEdge|vManage)", output, re.I)
                if model_match:
                    model = model_match.group(1)
                
                hostname_match = re.search(r"hostname\s+(\S+)", output, re.I)
                if hostname_match:
                    hostname = hostname_match.group(1)
            
            elif "huawei" in output_lower:
                vendor = "huawei"
                # 解析华为版本信息
                import re
                version_match = re.search(r"VRP\s+\(R\)\s+software,\s+Version\s+(\S+)", output)
                if version_match:
                    version = version_match.group(1)
            
            elif "fortinet" in output_lower:
                vendor = "fortinet"
                # 解析Fortinet版本信息
                import re
                version_match = re.search(r"FortiOS\s+v?(\S+)", output)
                if version_match:
                    version = version_match.group(1)
            
            return DeviceInfo(
                vendor=vendor,
                model=model,
                version=version,
                hostname=hostname
            )
            
        except Exception:
            return DeviceInfo(
                vendor="unknown",
                model="unknown",
                version="unknown",
                hostname="unknown"
            )
    
    async def _detect_device_type(self, client: paramiko.SSHClient) -> str:
        """检测设备类型"""
        try:
            # 尝试执行show version
            stdin, stdout, stderr = client.exec_command("show version", timeout=5)
            output = stdout.read().decode("utf-8", errors="ignore").lower()
            
            if "cisco" in output:
                return "cisco_sdwan"
            elif "huawei" in output:
                return "huawei"
            elif "fortinet" in output or "fortios" in output:
                return "fortinet"
            else:
                return "generic"
                
        except Exception:
            return "generic"
    
    async def _collect_cisco_sdwan_config(self, client: paramiko.SSHClient) -> Dict[str, Any]:
        """收集Cisco SD-WAN配置"""
        config = {}
        
        try:
            # 基础信息
            config["show_version"] = await self._execute_simple_command(client, "show version")
            config["show_hostname"] = await self._execute_simple_command(client, "show hostname")
            
            # 接口信息
            config["show_interface"] = await self._execute_simple_command(client, "show interface")
            config["show_ip_interface_brief"] = await self._execute_simple_command(client, "show ip interface brief")
            
            # 路由信息
            config["show_ip_route"] = await self._execute_simple_command(client, "show ip route")
            config["show_ip_route_vrf"] = await self._execute_simple_command(client, "show ip route vrf 1")
            
            # SD-WAN信息
            config["show_sdwan_policy"] = await self._execute_simple_command(client, "show sdwan policy")
            config["show_sdwan_bfd_sessions"] = await self._execute_simple_command(client, "show sdwan bfd sessions")
            config["show_sdwan_control_connections"] = await self._execute_simple_command(client, "show sdwan control connections")
            config["show_sdwan_omp_peers"] = await self._execute_simple_command(client, "show sdwan omp peers")
            
            # NAT信息
            config["show_ip_nat_translations"] = await self._execute_simple_command(client, "show ip nat translations")
            
            # 隧道信息
            config["show_sdwan_tunnel_statistics"] = await self._execute_simple_command(client, "show sdwan tunnel statistics")
            
        except Exception as e:
            config["error"] = str(e)
        
        return config
    
    async def _collect_huawei_config(self, client: paramiko.SSHClient) -> Dict[str, Any]:
        """收集华为设备配置"""
        config = {}
        
        try:
            # 基础信息
            config["display_version"] = await self._execute_simple_command(client, "display version")
            config["display_device"] = await self._execute_simple_command(client, "display device")
            
            # 接口信息
            config["display_interface"] = await self._execute_simple_command(client, "display interface")
            config["display_ip_interface"] = await self._execute_simple_command(client, "display ip interface")
            
            # 路由信息
            config["display_ip_routing_table"] = await self._execute_simple_command(client, "display ip routing-table")
            
            # VPN信息
            config["display_bgp_vpnv4_all_routing_table"] = await self._execute_simple_command(client, "display bgp vpnv4 all routing-table")
            
        except Exception as e:
            config["error"] = str(e)
        
        return config
    
    async def _collect_fortinet_config(self, client: paramiko.SSHClient) -> Dict[str, Any]:
        """收集Fortinet设备配置"""
        config = {}
        
        try:
            # 基础信息
            config["get_system_status"] = await self._execute_simple_command(client, "get system status")
            
            # 接口信息
            config["get_system_interface"] = await self._execute_simple_command(client, "get system interface")
            
            # 路由信息
            config["get_router_info_routing_table"] = await self._execute_simple_command(client, "get router info routing-table")
            
            # VPN信息
            config["diagnose_vpn_tunnel_list"] = await self._execute_simple_command(client, "diagnose vpn tunnel list")
            
        except Exception as e:
            config["error"] = str(e)
        
        return config
    
    async def _collect_generic_config(self, client: paramiko.SSHClient) -> Dict[str, Any]:
        """收集通用设备配置"""
        config = {}
        
        try:
            # 尝试常见命令
            commands = [
                ("uname -a", "system_info"),
                ("hostname", "hostname"),
                ("ifconfig -a", "interfaces"),
                ("ip addr show", "ip_addresses"),
                ("route -n", "routing_table"),
                ("netstat -rn", "netstat_routing"),
                ("cat /etc/resolv.conf", "dns_config"),
            ]
            
            for cmd, key in commands:
                try:
                    result = await self._execute_simple_command(client, cmd, timeout=5)
                    config[key] = result
                except Exception:
                    config[key] = f"命令执行失败: {cmd}"
            
        except Exception as e:
            config["error"] = str(e)
        
        return config
    
    async def _execute_simple_command(self, client: paramiko.SSHClient, command: str, timeout: int = 10) -> str:
        """执行简单命令并返回输出"""
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            output = stdout.read().decode("utf-8", errors="ignore")
            return output.strip()
        except Exception as e:
            return f"命令执行失败: {command}, 错误: {str(e)}"
