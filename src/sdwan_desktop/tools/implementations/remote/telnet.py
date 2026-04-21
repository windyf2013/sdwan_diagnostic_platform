"""Telnet适配器 - 远程设备连接"""

import asyncio
import telnetlib3
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import socket
import time

from ....core.types.context import Context
from ....tools.registry.decorator import tool_function
from ....tools.registry.dispatcher import ToolRequest


@dataclass
class TelnetConnection:
    """Telnet连接信息"""
    host: str
    port: int
    username: str
    password: str
    timeout: int = 30


@dataclass
class TelnetCommandResult:
    """Telnet命令执行结果"""
    command: str
    output: str
    duration_ms: float
    success: bool


@tool_function(
    name="telnet_adapter",
    description="Telnet远程设备连接",
    timeout=60,
    retry_count=1
)
class TelnetAdapter:
    """Telnet适配器 - 远程设备连接"""
    
    def __init__(self):
        self._connections: Dict[str, telnetlib3.TelnetReaderWriter] = {}
        self._connection_info: Dict[str, TelnetConnection] = {}
    
    async def execute(self, request: ToolRequest, ctx: Context) -> Dict[str, Any]:
        """执行Telnet操作"""
        action = request.params.get("action", "connect")
        
        if action == "connect":
            return await self._connect(request.params)
        elif action == "execute":
            return await self._execute_command(request.params)
        elif action == "disconnect":
            return await self._disconnect(request.params)
        else:
            return {
                "status": "error",
                "data": None,
                "error": f"未知操作: {action}"
            }
    
    async def _connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """建立Telnet连接"""
        host = params.get("host", "")
        port = params.get("port", 23)
        username = params.get("username", "")
        password = params.get("password", "")
        timeout = params.get("timeout", 30)
        
        if not host or not username or not password:
            return {
                "status": "error",
                "data": None,
                "error": "必须提供主机地址、用户名和密码"
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
            # 建立Telnet连接
            reader, writer = await telnetlib3.open_connection(
                host=host,
                port=port,
                timeout=timeout
            )
            
            # 等待登录提示
            await asyncio.sleep(1)
            
            # 读取欢迎信息
            welcome = await reader.read(1024)
            
            # 发送用户名
            writer.write(username + "\r\n")
            await writer.drain()
            await asyncio.sleep(0.5)
            
            # 读取密码提示
            password_prompt = await reader.read(1024)
            
            # 发送密码
            writer.write(password + "\r\n")
            await writer.drain()
            await asyncio.sleep(0.5)
            
            # 读取登录结果
            login_result = await reader.read(1024)
            
            # 检查是否登录成功
            login_success = True
            if "login incorrect" in login_result.lower() or "access denied" in login_result.lower():
                login_success = False
                writer.close()
                await writer.wait_closed()
                
                return {
                    "status": "error",
                    "data": None,
                    "error": "登录失败: 用户名或密码错误"
                }
            
            # 保存连接
            self._connections[connection_id] = (reader, writer)
            self._connection_info[connection_id] = TelnetConnection(
                host=host,
                port=port,
                username=username,
                password=password,
                timeout=timeout
            )
            
            return {
                "status": "success",
                "data": {
                    "connection_id": connection_id,
                    "welcome_message": welcome[:200],  # 只返回前200个字符
                    "message": "连接成功"
                },
                "error": None
            }
            
        except ConnectionRefusedError as e:
            return {
                "status": "error",
                "data": None,
                "error": f"连接被拒绝: {str(e)}"
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
        """执行Telnet命令"""
        connection_id = params.get("connection_id", "")
        command = params.get("command", "")
        timeout = params.get("timeout", 10)
        
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
        
        reader, writer = self._connections[connection_id]
        
        try:
            start_time = time.time()
            
            # 发送命令
            writer.write(command + "\r\n")
            await writer.drain()
            
            # 等待命令执行
            await asyncio.sleep(1)
            
            # 读取输出
            output = ""
            try:
                # 设置超时
                async with asyncio.timeout(timeout):
                    while True:
                        chunk = await reader.read(1024)
                        if not chunk:
                            break
                        output += chunk
                        
                        # 检查是否收到命令提示符
                        if ">" in chunk or "#" in chunk or "$" in chunk:
                            break
                            
            except asyncio.TimeoutError:
                # 超时后返回已读取的内容
                pass
            
            duration_ms = (time.time() - start_time) * 1000
            
            # 清理输出（移除回显的命令）
            lines = output.split('\n')
            cleaned_lines = []
            for line in lines:
                if line.strip() != command.strip():
                    cleaned_lines.append(line)
            
            cleaned_output = '\n'.join(cleaned_lines).strip()
            
            result = TelnetCommandResult(
                command=command,
                output=cleaned_output,
                duration_ms=duration_ms,
                success=True
            )
            
            return {
                "status": "success",
                "data": {
                    "result": {
                        "command": result.command,
                        "output": result.output,
                        "duration_ms": result.duration_ms,
                        "success": result.success
                    }
                },
                "error": None
            }
            
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "error": f"命令执行失败: {str(e)}"
            }
    
    async def _disconnect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """断开Telnet连接"""
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
            reader, writer = self._connections[connection_id]
            
            # 发送退出命令
            writer.write("exit\r\n")
            await writer.drain()
            await asyncio.sleep(0.5)
            
            # 关闭连接
            writer.close()
            await writer.wait_closed()
            
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
    
    async def test_connectivity(self, host: str, port: int = 23, timeout: int = 5) -> Dict[str, Any]:
        """测试Telnet连通性"""
        try:
            # 尝试建立TCP连接
            reader, writer = await asyncio.wait_for(
                telnetlib3.open_connection(host=host, port=port),
                timeout=timeout
            )
            
            # 读取banner
            banner = await asyncio.wait_for(reader.read(1024), timeout=2)
            
            # 关闭连接
            writer.close()
            await writer.wait_closed()
            
            return {
                "status": "success",
                "data": {
                    "reachable": True,
                    "banner": banner[:200] if banner else "",
                    "port_open": True
                },
                "error": None
            }
            
        except ConnectionRefusedError:
            return {
                "status": "success",
                "data": {
                    "reachable": False,
                    "banner": "",
                    "port_open": False
                },
                "error": None
            }
        except (socket.timeout, asyncio.TimeoutError):
            return {
                "status": "success",
                "data": {
                    "reachable": False,
                    "banner": "",
                    "port_open": False
                },
                "error": None
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "error": f"测试失败: {str(e)}"
            }
    
    async def execute_sequence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行命令序列"""
        connection_id = params.get("connection_id", "")
        commands = params.get("commands", [])
        delay_between_commands = params.get("delay_between_commands", 1)
        
        if not connection_id or not commands:
            return {
                "status": "error",
                "data": None,
                "error": "必须提供连接ID和命令列表"
            }
        
        if connection_id not in self._connections:
            return {
                "status": "error",
                "data": None,
                "error": f"连接不存在: {connection_id}"
            }
        
        results = []
        
        try:
            for command in commands:
                # 执行单个命令
                result = await self._execute_command({
                    "connection_id": connection_id,
                    "command": command
                })
                
                if result["status"] == "success":
                    results.append({
                        "command": command,
                        "success": True,
                        "output": result["data"]["result"]["output"]
                    })
                else:
                    results.append({
                        "command": command,
                        "success": False,
                        "error": result["error"]
                    })
                
                # 等待指定时间
                await asyncio.sleep(delay_between_commands)
            
            return {
                "status": "success",
                "data": {
                    "results": results
                },
                "error": None
            }
            
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "error": f"命令序列执行失败: {str(e)}"
            }
