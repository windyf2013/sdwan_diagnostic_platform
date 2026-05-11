"""
CPE 采集服务

通过 SSH/TELNET 远程连接 CPE 设备，执行配置采集命令并自动解析。
遵循 SDWAN_SPEC.md §2.4 工具系统规范
遵循 detail_function_design.md §3.1 CPE 采集服务设计
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import paramiko

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.services.collector.base import BaseCollector, CollectorConfig, CollectorResult
from sdwan_desktop.services.parser.vendor import ConfigParserRegistry

logger = logging.getLogger(__name__)


class CpeCollectorConfig(CollectorConfig):
    """CPE 采集器专用配置"""
    
    def __init__(
        self,
        host: str = "",
        port: int = 22,
        username: str = "",
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        protocol: str = "ssh",
        command_timeout: int = 10,
        connect_timeout: int = 30,
        device_type: str = "generic",
        timeout_seconds: int = 60,
        retry_count: int = 1,
        collect_interval: int = 300,
        enable_parallel: bool = True,
        max_workers: int = 5
    ):
        super().__init__(
            device_type=device_type,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            collect_interval=collect_interval,
            enable_parallel=enable_parallel,
            max_workers=max_workers
        )
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.protocol = protocol
        self.command_timeout = command_timeout
        self.connect_timeout = connect_timeout


class CpeCollector(BaseCollector):
    """CPE 采集器
    
    通过 SSH/TELNET 连接 CPE 设备，执行配置采集命令并自动解析为结构化数据。
    
    工作流程：
    1. 建立 SSH/TELNET 连接
    2. 执行版本检测命令，自动识别厂商
    3. 根据厂商加载对应的命令模板
    4. 按优先级分组执行采集命令
    5. 调用对应厂商的解析器解析配置
    6. 返回结构化的 CpeConfiguration 对象
    
    特性：
    - 自动识别厂商（Cisco SD-WAN / Huawei / Fortinet 等）
    - 命令失败降级（单个命令失败不影响整体采集）
    - 局部失败不影响整体（部分命令超时跳过继续执行）
    - 敏感信息不入日志（密码、私钥等不记录到日志）
    """
    
    def __init__(self, config: Optional[CpeCollectorConfig] = None):
        """初始化 CPE 采集器
        
        Args:
            config: CPE 采集器配置
        """
        super().__init__(config or CpeCollectorConfig())
        self._client: Optional[paramiko.SSHClient] = None
        self._telnet_reader: Optional[Any] = None
        self._telnet_writer: Optional[Any] = None
        self._connection_id: Optional[str] = None
        self._raw_outputs: Dict[str, str] = {}
    
    async def collect(self, ctx: FlowContext) -> CollectorResult:
        """执行 CPE 配置采集
        
        Args:
            ctx: 流程上下文
            
        Returns:
            采集结果（data 字段包含 CpeConfiguration 对象）
        """
        start_time = time.time()
        
        try:
            # 1. 验证配置
            if not await self.validate(ctx):
                return CollectorResult(
                    success=False,
                    error_message="CPE 采集器配置无效",
                    duration_ms=(time.time() - start_time) * 1000,
                )
            
            # 2. 建立连接
            logger.info(f"正在连接 CPE 设备: {self.config.host}:{self.config.port}")
            await self._connect()
            
            # 3. 检测设备类型
            device_type = await self._detect_device_type()
            logger.info(f"检测到设备类型: {device_type}")
            
            # 4. 加载命令模板
            commands = self._load_command_template(device_type)
            if not commands:
                return CollectorResult(
                    success=False,
                    error_message=f"未找到设备类型 '{device_type}' 的命令模板",
                    duration_ms=(time.time() - start_time) * 1000,
                )
            
            # 5. 执行采集命令（按优先级分组）
            await self._execute_commands(commands)
            
            # 6. 解析配置
            parser = ConfigParserRegistry.get_parser(device_type)
            if not parser:
                return CollectorResult(
                    success=False,
                    error_message=f"未找到设备类型 '{device_type}' 的解析器",
                    duration_ms=(time.time() - start_time) * 1000,
                )
            
            cpe_config = parser.parse_all(self._raw_outputs)
            
            # 7. 断开连接
            await self._disconnect()
            
            duration_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"CPE 配置采集完成: vendor={cpe_config.vendor}, "
                f"model={cpe_config.model}, version={cpe_config.version}, "
                f"耗时={duration_ms:.0f}ms"
            )
            
            return CollectorResult(
                success=True,
                data={"cpe_configuration": cpe_config},
                collected_items=list(self._raw_outputs.keys()),
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"CPE 配置采集失败: {e}", exc_info=True)
            
            # 确保断开连接
            try:
                await self._disconnect()
            except Exception:
                pass
            
            return CollectorResult(
                success=False,
                error_message=f"CPE 配置采集失败: {str(e)}",
                duration_ms=duration_ms,
            )
    
    async def validate(self, ctx: FlowContext) -> bool:
        """验证采集器配置是否有效
        
        Args:
            ctx: 流程上下文
            
        Returns:
            配置是否有效
        """
        if not isinstance(self.config, CpeCollectorConfig):
            logger.warning("配置类型错误：需要 CpeCollectorConfig")
            return False
        
        if not self.config.host:
            logger.warning("缺少主机地址")
            return False
        
        if not self.config.username:
            logger.warning("缺少用户名")
            return False
        
        if self.config.protocol == "ssh" and not self.config.password and not self.config.private_key:
            logger.warning("SSH 协议需要提供密码或私钥")
            return False
        
        if self.config.protocol not in ["ssh", "telnet"]:
            logger.warning(f"不支持的协议: {self.config.protocol}")
            return False
        
        return True
    
    async def _connect(self):
        """建立 SSH/TELNET 连接"""
        if self.config.protocol == "ssh":
            await self._connect_ssh()
        elif self.config.protocol == "telnet":
            await self._connect_telnet()
        else:
            raise NotImplementedError(f"协议 '{self.config.protocol}' 暂未实现")
    
    async def _connect_ssh(self):
        """建立 SSH 连接"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_params = {
                "hostname": self.config.host,
                "port": self.config.port,
                "username": self.config.username,
                "timeout": self.config.connect_timeout,
            }
            
            if self.config.password:
                connect_params["password"] = self.config.password
            elif self.config.private_key:
                import io
                key_file = io.StringIO(self.config.private_key)
                pkey = paramiko.RSAKey.from_private_key(key_file)
                connect_params["pkey"] = pkey
            
            # 使用线程池执行阻塞操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.connect(**connect_params)
            )
            
            self._client = client
            self._connection_id = f"{self.config.host}:{self.config.port}:{self.config.username}"
            
            logger.info(f"SSH 连接成功: {self._connection_id}")
            
        except paramiko.AuthenticationException as e:
            raise ConnectionError(f"SSH 认证失败: {str(e)}")
        except paramiko.SSHException as e:
            raise ConnectionError(f"SSH 连接失败: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"连接失败: {str(e)}")
    
    async def _connect_telnet(self):
        """建立 Telnet 连接"""
        try:
            # 使用 telnetlib3 建立异步 Telnet 连接
            import telnetlib3
            
            loop = asyncio.get_event_loop()
            
            # 建立连接（带超时）
            self._telnet_reader, self._telnet_writer = await asyncio.wait_for(
                telnetlib3.open_connection(
                    host=self.config.host,
                    port=self.config.port
                ),
                timeout=self.config.connect_timeout
            )
            
            self._connection_id = f"{self.config.host}:{self.config.port}:{self.config.username}"
            
            # 读取初始 banner
            try:
                banner = await asyncio.wait_for(
                    self._telnet_reader.read(1024),
                    timeout=5
                )
                logger.debug(f"Telnet Banner: {banner[:200]}")
            except asyncio.TimeoutError:
                logger.debug("Telnet Banner 读取超时，继续执行")
            
            # 等待登录提示
            await self._wait_for_prompt(["login:", "username:", "user:"])
            
            # 发送用户名
            self._telnet_writer.write(f"{self.config.username}\r\n")
            await self._telnet_writer.drain()
            
            # 等待密码提示
            await self._wait_for_prompt(["password:", "passwd:"])
            
            # 发送密码
            if self.config.password:
                self._telnet_writer.write(f"{self.config.password}\r\n")
                await self._telnet_writer.drain()
            else:
                raise ConnectionError("Telnet 连接需要提供密码")
            
            # 等待一小段时间，让设备处理登录
            await asyncio.sleep(2)
            
            # 尝试读取登录后的初始输出，用于调试
            try:
                initial_output = await asyncio.wait_for(
                    self._telnet_reader.read(2048),
                    timeout=3
                )
                logger.debug(f"登录后初始输出: {repr(initial_output[:500])}")
            except asyncio.TimeoutError:
                logger.debug("登录后无初始输出")
            
            # 尝试发送一个回车键，触发命令提示符显示
            self._telnet_writer.write("\r\n")
            await self._telnet_writer.drain()
            await asyncio.sleep(1)
            
            # 等待登录成功后的提示符（增加更多常见提示符和延长超时）
            shell_prompts = [">", "#", "$", "]>", ")", "login", "Welcome"]
            await self._wait_for_prompt(shell_prompts, timeout=20)
            
            logger.info(f"Telnet 连接成功: {self._connection_id}")
            
        except asyncio.TimeoutError:
            raise ConnectionError(f"Telnet 连接超时: {self.config.host}:{self.config.port}")
        except ConnectionRefusedError:
            raise ConnectionError(f"Telnet 连接被拒绝: {self.config.host}:{self.config.port}")
        except Exception as e:
            raise ConnectionError(f"Telnet 连接失败: {str(e)}")
    
    async def _wait_for_prompt(self, prompts: List[str], timeout: int = 5):
        """等待特定的提示符
        
        Args:
            prompts: 要等待的提示符列表
            timeout: 超时时间（秒）
        """
        try:
            buffer = ""
            start_time = asyncio.get_event_loop().time()
            
            while True:
                # 检查超时
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise asyncio.TimeoutError(f"等待提示符超时: {prompts}")
                
                # 读取一个字符
                char = await asyncio.wait_for(
                    self._telnet_reader.read(1),
                    timeout=1
                )
                
                if not char:
                    continue
                
                buffer += char
                
                # 检查是否匹配任何提示符
                for prompt in prompts:
                    if prompt.lower() in buffer.lower():
                        logger.debug(f"检测到提示符: {prompt}")
                        return
                
                # 限制缓冲区大小
                if len(buffer) > 1024:
                    buffer = buffer[-512:]
                    
        except asyncio.TimeoutError:
            raise
    
    async def _execute_command_telnet(self, command: str, timeout: int = 10) -> str:
        """通过 Telnet 执行命令
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            
        Returns:
            命令输出字符串
        """
        if not self._telnet_writer:
            raise ConnectionError("未建立 Telnet 连接")
        
        try:
            # 发送命令
            self._telnet_writer.write(f"{command}\r\n")
            await self._telnet_writer.drain()
            
            # 读取输出，直到遇到提示符
            output = ""
            start_time = asyncio.get_event_loop().time()
            
            while True:
                # 检查超时
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.warning(f"命令 '{command}' 执行超时")
                    break
                
                # 尝试读取输出
                try:
                    chunk = await asyncio.wait_for(
                        self._telnet_reader.read(4096),
                        timeout=2
                    )
                    
                    if not chunk:
                        # 短暂延迟后检查是否完成
                        await asyncio.sleep(0.5)
                        continue
                    
                    # telnetlib3 返回的已经是字符串，不需要 decode
                    output += chunk
                    
                    # 检查是否回到提示符（简单判断）
                    if output.strip().endswith(("#", ">")):
                        break
                        
                except asyncio.TimeoutError:
                    # 读取超时，可能命令已完成
                    break
            
            return output.strip()
            
        except Exception as e:
            raise CommandExecutionError(f"Telnet 命令执行失败 '{command}': {str(e)}")
    
    async def _detect_device_type(self) -> str:
        """检测设备类型
        
        执行 show version 命令，通过 ConfigParserRegistry 自动检测厂商。
        
        Returns:
            设备类型标识（如 "cisco_sdwan"）
        """
        try:
            version_output = await self._execute_command("show version", timeout=10)
            
            # 尝试所有已注册的解析器
            for vendor in ConfigParserRegistry.list_vendors():
                parser = ConfigParserRegistry.get_parser(vendor)
                if parser and parser.detect_vendor(version_output):
                    logger.info(f"自动检测到设备厂商: {vendor}")
                    return vendor
            
            logger.warning(f"无法识别设备类型，默认使用 generic")
            return "generic"
            
        except Exception as e:
            logger.warning(f"设备类型检测失败: {e}，默认使用 generic")
            return "generic"
    
    def _load_command_template(self, device_type: str) -> List[Dict[str, Any]]:
        """加载命令模板
        
        Args:
            device_type: 设备类型标识
            
        Returns:
            命令列表（按优先级排序）
        """
        # TODO: 从 YAML 配置文件加载命令模板
        # 当前使用硬编码的 Cisco SD-WAN 命令列表作为示例
        
        if device_type == "cisco_sdwan":
            return [
                {"name": "show version", "priority": 1, "optional": False},
                {"name": "show running-config", "priority": 1, "optional": False},
                {"name": "show interface", "priority": 2, "optional": False},
                {"name": "show ip route", "priority": 2, "optional": False},
                {"name": "show sdwan policy", "priority": 3, "optional": True},
                {"name": "show sdwan bfd sessions", "priority": 2, "optional": False},
                {"name": "show ip nat translations", "priority": 3, "optional": True},
            ]
        else:
            logger.warning(f"未知设备类型 '{device_type}'，使用默认命令集")
            return [
                {"name": "show version", "priority": 1, "optional": False},
                {"name": "show interface", "priority": 2, "optional": True},
                {"name": "show ip route", "priority": 2, "optional": True},
            ]
    
    async def _execute_commands(self, commands: List[Dict[str, Any]]):
        """执行采集命令（按优先级分组）
        
        Args:
            commands: 命令列表
        """
        # 按优先级分组
        priority_groups: Dict[int, List[Dict[str, Any]]] = {}
        for cmd in commands:
            priority = cmd.get("priority", 99)
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(cmd)
        
        # 按优先级顺序执行
        for priority in sorted(priority_groups.keys()):
            group = priority_groups[priority]
            logger.info(f"执行优先级 {priority} 的命令组（共 {len(group)} 个命令）")
            
            for cmd in group:
                cmd_name = cmd["name"]
                optional = cmd.get("optional", False)
                
                try:
                    output = await self._execute_command(cmd_name, timeout=self.config.command_timeout)
                    self._raw_outputs[cmd_name] = output
                    logger.debug(f"命令 '{cmd_name}' 执行成功（输出长度: {len(output)}）")
                    
                except Exception as e:
                    if optional:
                        logger.warning(f"可选命令 '{cmd_name}' 执行失败，跳过: {e}")
                        self._raw_outputs[cmd_name] = ""
                    else:
                        logger.error(f"必需命令 '{cmd_name}' 执行失败: {e}")
                        raise
    
    async def _execute_command(self, command: str, timeout: int = 10) -> str:
        """执行单个命令
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            
        Returns:
            命令输出字符串
        """
        # 根据协议类型选择执行方式
        if self.config.protocol == "ssh":
            return await self._execute_command_ssh(command, timeout)
        elif self.config.protocol == "telnet":
            return await self._execute_command_telnet(command, timeout)
        else:
            raise NotImplementedError(f"协议 '{self.config.protocol}' 暂未实现")
    
    async def _execute_command_ssh(self, command: str, timeout: int = 10) -> str:
        """通过 SSH 执行命令
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            
        Returns:
            命令输出字符串
        """
        if not self._client:
            raise ConnectionError("未建立 SSH 连接")
        
        try:
            loop = asyncio.get_event_loop()
            
            stdin, stdout, stderr = await loop.run_in_executor(
                None,
                lambda: self._client.exec_command(command, timeout=timeout)
            )
            
            stdout_str = await loop.run_in_executor(None, stdout.read)
            stderr_str = await loop.run_in_executor(None, stderr.read)
            
            output = stdout_str.decode("utf-8", errors="ignore").strip()
            error_output = stderr_str.decode("utf-8", errors="ignore").strip()
            
            if error_output:
                logger.warning(f"命令 '{command}' 标准错误输出: {error_output[:200]}")
            
            return output
            
        except Exception as e:
            raise CommandExecutionError(f"SSH 命令执行失败 '{command}': {str(e)}")
    
    async def _disconnect(self):
        """断开连接"""
        if self.config.protocol == "ssh" and self._client:
            try:
                self._client.close()
                logger.info(f"SSH 连接已断开: {self._connection_id}")
            except Exception as e:
                logger.warning(f"断开 SSH 连接时出错: {e}")
            finally:
                self._client = None
                self._connection_id = None
        elif self.config.protocol == "telnet" and self._telnet_writer:
            try:
                # 发送退出命令
                self._telnet_writer.write("exit\r\n")
                await self._telnet_writer.drain()
                await asyncio.sleep(0.5)
                
                # 关闭连接
                self._telnet_writer.close()
                if hasattr(self._telnet_writer, 'wait_closed'):
                    await self._telnet_writer.wait_closed()
                
                logger.info(f"Telnet 连接已断开: {self._connection_id}")
            except Exception as e:
                logger.warning(f"断开 Telnet 连接时出错: {e}")
            finally:
                self._telnet_reader = None
                self._telnet_writer = None
                self._connection_id = None
    
    def get_supported_items(self) -> List[str]:
        """获取支持采集的项目列表
        
        Returns:
            支持的项目名称列表
        """
        return [
            "version",
            "interfaces",
            "routes",
            "sdwan_policies",
            "vpn_tunnels",
            "nat_rules",
        ]


class CommandExecutionError(Exception):
    """命令执行异常"""
    pass
