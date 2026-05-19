"""
CPE 采集服务

通过 SSH/TELNET 远程连接 CPE 设备，执行配置采集命令并自动解析。
遵循 SDWAN_SPEC.md §2.4 工具系统规范
遵循 detail_function_design.md §3.1 CPE 采集服务设计
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import paramiko

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.services.collector.base import BaseCollector, CollectorConfig, CollectorResult
from sdwan_desktop.services.collector.cpe_telnet_login import (
    build_telnet_login_error,
    diagnose_telnet_login_failure,
    format_telnet_eof_error,
    redact_secrets,
)
from sdwan_desktop.services.collector.raisecom_interface_discovery import (
    build_raisecom_extra_show_interface_commands,
)
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
        max_workers: int = 5,
        testnode_password: Optional[str] = None,
        preset_view_passwords: Optional[Mapping[str, Optional[str]]] = None,
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
        self.testnode_password = testnode_password
        self.preset_view_passwords: Dict[str, Optional[str]] = dict(preset_view_passwords or {})


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
        self._telnet_login_transcript: str = ""
        self._connection_id: Optional[str] = None
        self._telnet_diagnose_via_testnode: bool = False
        self._active_device_type: Optional[str] = None
        self._raw_outputs: Dict[str, str] = {}
        # RCIOS：未配置 hostname 时为 host# / host>；配置后为 <name># / <name(test-node)# 等（勿写死 host）
        # bash 子 shell 单独列出，避免与「任意标识符#」混淆
        self._telnet_prompt_regex = re.compile(
            r"(?:bash-\d+\.\d+#|[a-zA-Z][a-zA-Z0-9._-]*(?:\([^)]+\))?[#>])\s*$",
            re.MULTILINE,
        )
        # 用户视图（非特权）：行尾 name>，用于判断是否需要 enable
        self._raisecom_user_exec_prompt = re.compile(
            r"(?m)[a-zA-Z][a-zA-Z0-9._-]*>\s*$",
        )
        # diagnose 入口不得以 host# 作为结束条件；此处用宽松匹配识别 bash 子 shell（行内任意位置）
        self._bash_diag_marker = re.compile(r"(?i)bash-[0-9][^\r\n]*#")
        # 5200B 经 su（及部分 diagnose 固件）进入 busybox/ash 时提示符为单独一行的 root ``#``，非 ``bash-N.N#``
        self._root_diag_shell_prompt = re.compile(r"(?m)(?:^|\r?\n)\s*#\s*$")
        # 分页提示须先于特权提示符匹配，避免配置行尾误匹配 ``name#`` 导致截断
        self._cli_more_marker = re.compile(r"--More--", re.IGNORECASE)

    def _preset_views(self) -> Dict[str, Optional[str]]:
        if isinstance(self.config, CpeCollectorConfig) and self.config.preset_view_passwords:
            return dict(self.config.preset_view_passwords)
        return {}

    def _password_for_view(self, view: str) -> Optional[str]:
        """二次认证视图口令：设备级覆盖 > 通用视图文件 > 登录密码。"""
        v = (view or "").strip().lower()
        cfg = self.config
        preset = self._preset_views()

        if v == "testnode":
            if isinstance(cfg, CpeCollectorConfig) and cfg.testnode_password:
                return cfg.testnode_password
            if preset.get("testnode"):
                return preset["testnode"]
            return cfg.password

        if v == "diagnose":
            if preset.get("diagnose"):
                return preset["diagnose"]
            if isinstance(cfg, CpeCollectorConfig) and cfg.testnode_password:
                return cfg.testnode_password
            if preset.get("testnode"):
                return preset["testnode"]
            return cfg.password

        if v == "su":
            if preset.get("su"):
                return preset["su"]
            return cfg.password

        if v == "enable":
            if preset.get("enable"):
                return preset["enable"]
            return cfg.password

        return cfg.password

    @staticmethod
    def _sanitize_cli_pagination(output: str) -> str:
        """去掉 RCIOS ``--More--`` 分页标记及同行粘连续行，避免 running-config 解析断裂。"""
        if not output or "--more--" not in output.lower():
            return output
        lines: List[str] = []
        for line in output.replace("\r", "").split("\n"):
            if "--More--" not in line and "--more--" not in line.lower():
                lines.append(line)
                continue
            rest = re.sub(r"^.*?--More--\s*(?:\([^)]*\))?\s*", "", line, count=1, flags=re.IGNORECASE)
            if rest.strip():
                lines.append(rest)
        return "\n".join(lines)

    @staticmethod
    def _raisecom_url_group_count(running_config: str) -> int:
        """running-config 中 ``url-group`` 块数量（用于判断是否需采集 policy table 100）。"""
        if not running_config:
            return 0
        return len(re.findall(r"(?m)^url-group\s+\S+", running_config))

    def _diagnostic_shell_prompt_seen(self, text: str) -> bool:
        """是否已出现诊断 Linux shell 提示符（bash 子 shell 或单独一行的 root ``#``）。
        注意：RCIOS 特权提示符 ``host#`` / ``xxx#`` 由 ``_telnet_prompt_regex`` 匹配，勿与本条混淆。
        """
        normalized = text.replace("\r", "")
        return bool(
            self._bash_diag_marker.search(normalized)
            or self._root_diag_shell_prompt.search(normalized)
        )

    async def collect(self, ctx: FlowContext) -> CollectorResult:
        """执行 CPE 配置采集
        
        Args:
            ctx: 流程上下文
            
        Returns:
            采集结果（data 字段包含 CpeConfiguration 对象）
        """
        start_time = time.time()
        self._raw_outputs = {}
        self._active_device_type = None

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
            self._active_device_type = device_type
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
            # 5b. Raisecom：按 running-config / 路由 / link detect 推断 overlay 等接口，补采 show interface
            if device_type in ("raisecom_msg5200", "raisecom_msg5200b"):
                extra_iface_cmds = build_raisecom_extra_show_interface_commands(self._raw_outputs)
                if extra_iface_cmds:
                    logger.info(
                        "Raisecom 追加接口采集: %d 条 show interface（vxlan/ipsec/l2tp/tunnel 等）",
                        len(extra_iface_cmds),
                    )
                    await self._execute_commands(extra_iface_cmds)

            # 6. 解析配置
            parser = ConfigParserRegistry.get_parser(device_type)
            if not parser:
                return CollectorResult(
                    success=False,
                    error_message=f"未找到设备类型 '{device_type}' 的解析器",
                    duration_ms=(time.time() - start_time) * 1000,
                )
            
            cpe_config = parser.parse_all(self._raw_outputs)
            artifact_paths = self._persist_collected_artifacts(ctx, device_type, cpe_config)
            
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
                data={
                    "cpe_configuration": cpe_config,
                    "artifact_paths": artifact_paths,
                    "device_type": device_type,
                },
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
            
            err_text = str(e)
            if err_text.startswith("Telnet 登录失败"):
                error_message = err_text
            else:
                error_message = f"CPE 配置采集失败: {err_text}"
            return CollectorResult(
                success=False,
                error_message=error_message,
                duration_ms=duration_ms,
            )

    async def run_probe_commands(
        self,
        ctx: FlowContext,
        commands: List[Dict[str, Any]],
    ) -> CollectorResult:
        """在拓扑构建之后执行补充探测命令（二次连接）。

        与 ``collect`` 解耦：主采集结束后会断开连接；本方法独立建连、执行、断开。
        ``FlowContext`` 中应已设置 ``cpe_device_type``（与主采集 ``device_type`` 一致），
        避免二次指纹误判导致 5200B 误走 ``diagnose`` 而非 ``su``。

        Args:
            ctx: 流程上下文（读取 ``cpe_device_type``）。
            commands: 与 ``_load_command_template`` 相同结构的命令列表。

        Returns:
            ``CollectorResult``；成功时 ``data`` 含 ``raw_outputs``、``device_type``。
        """
        start_time = time.time()
        self._raw_outputs = {}
        self._active_device_type = None
        try:
            if not await self.validate(ctx):
                return CollectorResult(
                    success=False,
                    error_message="CPE 采集器配置无效",
                    duration_ms=(time.time() - start_time) * 1000,
                )
            await self._connect()
            device_type = ctx.get("cpe_device_type")
            if not device_type:
                device_type = await self._detect_device_type()
            self._active_device_type = device_type
            logger.info("拓扑后探测：设备类型=%s", device_type)
            await self._execute_commands(commands)
            await self._disconnect()
            duration_ms = (time.time() - start_time) * 1000
            return CollectorResult(
                success=True,
                data={
                    "raw_outputs": dict(self._raw_outputs),
                    "device_type": device_type,
                },
                collected_items=list(self._raw_outputs.keys()),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning("拓扑后探测失败: %s", e, exc_info=True)
            try:
                await self._disconnect()
            except Exception:
                pass
            return CollectorResult(
                success=False,
                error_message=str(e),
                data={"raw_outputs": dict(self._raw_outputs)},
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
    
    def _telnet_login_secrets(self) -> List[Optional[str]]:
        return [self.config.password, self.config.testnode_password]

    def _telnet_record(self, chunk: Optional[str]) -> None:
        if chunk:
            self._telnet_login_transcript += chunk

    def _telnet_login_rejection(self, stage: str) -> Optional[ConnectionError]:
        transcript = redact_secrets(
            self._telnet_login_transcript, self._telnet_login_secrets()
        )
        if diagnose_telnet_login_failure(transcript):
            return self._telnet_login_error(stage)
        return None

    def _telnet_login_error(self, stage: str, *, timed_out: bool = False) -> ConnectionError:
        msg = build_telnet_login_error(
            stage=stage,
            host=self.config.host,
            port=self.config.port,
            transcript=self._telnet_login_transcript,
            secrets=self._telnet_login_secrets(),
            timed_out=timed_out,
        )
        logger.warning(msg)
        return ConnectionError(msg)

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
        self._telnet_login_transcript = ""
        try:
            # 使用 telnetlib3 建立异步 Telnet 连接
            import telnetlib3
            from telnetlib3.client import TelnetClient

            # stdin 为 TTY 时 telnetlib3 默认选用 TelnetTerminalClient：其 send_naws/send_env
            # 使用本机控制台窗口尺寸，常远大于 80x24；自动化场景强制 TelnetClient，使 NAWS
            # 与显式 term/cols/rows 一致（与常见固定终端档案的客户端行为对齐）。
            self._telnet_reader, self._telnet_writer = await asyncio.wait_for(
                telnetlib3.open_connection(
                    host=self.config.host,
                    port=self.config.port,
                    client_factory=TelnetClient,
                    term="vt100",
                    cols=80,
                    rows=24,
                    connect_timeout=float(self.config.connect_timeout),
                    # 不向设备上报本机 COLORTERM/USER/HOME 等，减少 NEW_ENVIRON 触发的兼容性问题
                    send_environ=("TERM", "LANG"),
                ),
                timeout=self.config.connect_timeout
            )
            
            self._connection_id = f"{self.config.host}:{self.config.port}:{self.config.username}"
            
            # 读取初始 banner（可能已含 Username:/login: 整行，避免再空等 _wait_for_prompt）
            banner = ""
            try:
                banner = await asyncio.wait_for(
                    self._telnet_reader.read(1024),
                    timeout=5
                )
                self._telnet_record(banner)
                logger.debug(f"Telnet Banner: {banner[:200]}")
            except asyncio.TimeoutError:
                logger.debug("Telnet Banner 读取超时，继续执行")

            login_hints = ("login:", "username:", "user:")
            if not any(h in (banner or "").lower() for h in login_hints):
                await self._wait_for_prompt(
                    ["login:", "username:", "user:"], timeout=10, stage="等待用户名提示"
                )
            
            # 发送用户名
            self._telnet_writer.write(f"{self.config.username}\r\n")
            await self._telnet_writer.drain()
            
            # 等待密码提示
            await self._wait_for_prompt(
                ["password:", "passwd:"], timeout=10, stage="等待密码提示"
            )
            
            # 发送密码
            if self.config.password:
                self._telnet_writer.write(f"{self.config.password}\r\n")
                await self._telnet_writer.drain()
            else:
                raise ConnectionError(
                    f"Telnet 登录失败（未配置密码）: {self.config.host}:{self.config.port}；"
                    "请在界面填写密码或配置 configs/cpe_credentials.yaml"
                )
            
            # 等待一小段时间，让设备处理登录
            await asyncio.sleep(2)
            
            try:
                initial_output = await asyncio.wait_for(
                    self._telnet_reader.read(2048),
                    timeout=3
                )
                self._telnet_record(initial_output)
                logger.debug(
                    "登录后初始输出: %s",
                    repr(redact_secrets(initial_output[:500], self._telnet_login_secrets())),
                )
            except asyncio.TimeoutError:
                logger.debug("登录后无初始输出")

            rejected = self._telnet_login_rejection("提交密码后")
            if rejected is not None:
                raise rejected
            
            # 尝试发送一个回车键，触发命令提示符显示
            self._telnet_writer.write("\r\n")
            await self._telnet_writer.drain()
            await asyncio.sleep(1)
            
            # 等待登录成功后的提示符（增加更多常见提示符和延长超时）
            shell_prompts = [">", "#", "$", "]>", ")", "login", "Welcome"]
            await self._wait_for_prompt(
                shell_prompts, timeout=20, stage="等待命令行提示符"
            )
            
            logger.info(f"Telnet 连接成功: {self._connection_id}")
            
        except ConnectionError:
            raise
        except asyncio.TimeoutError:
            raise self._telnet_login_error("登录", timed_out=True)
        except ConnectionRefusedError:
            raise ConnectionError(
                f"Telnet 连接被拒绝: {self.config.host}:{self.config.port}；"
                "请检查 IP、端口(23)及设备 Telnet 服务是否开启"
            )
        except Exception as e:
            if self._telnet_login_transcript:
                raise self._telnet_login_error("登录") from e
            raise ConnectionError(
                f"Telnet 连接失败: {self.config.host}:{self.config.port}；{e}"
            ) from e
    
    async def _wait_for_prompt(
        self, prompts: List[str], timeout: int = 5, *, stage: str = "等待设备响应"
    ) -> str:
        """等待特定的提示符
        
        Args:
            prompts: 要等待的提示符列表
            timeout: 超时时间（秒）
            stage: 失败时写入用户可见错误信息的阶段描述
        """
        buffer = ""
        start_time = asyncio.get_event_loop().time()
        try:
            while True:
                if asyncio.get_event_loop().time() - start_time > timeout:
                    self._telnet_record(buffer)
                    rejected = self._telnet_login_rejection(stage)
                    if rejected is not None:
                        raise rejected
                    raise self._telnet_login_error(stage, timed_out=True)

                char = await asyncio.wait_for(
                    self._telnet_reader.read(1),
                    timeout=1
                )

                if not char:
                    self._telnet_record(buffer)
                    raise ConnectionError(
                        format_telnet_eof_error(
                            host=self.config.host,
                            port=self.config.port,
                            transcript=self._telnet_login_transcript,
                            secrets=self._telnet_login_secrets(),
                        )
                    )

                buffer += char
                self._telnet_record(char)

                for prompt in prompts:
                    if prompt.lower() in buffer.lower():
                        logger.debug(f"检测到提示符: {prompt}")
                        return buffer

                if len(buffer) > 1024:
                    buffer = buffer[-512:]

        except asyncio.TimeoutError:
            self._telnet_record(buffer)
            rejected = self._telnet_login_rejection(stage)
            if rejected is not None:
                raise rejected
            raise self._telnet_login_error(stage, timed_out=True) from None
    
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
            if command.startswith("testnode:"):
                await self._enter_testnode_view(timeout=timeout)
                try:
                    return await self._execute_telnet_plain(command.split(":", 1)[1], timeout=timeout)
                finally:
                    try:
                        # RCIOS：test-node 仅用于少量命令，结束后须 ``end`` 回到 enable，避免后续命令误入 test-node
                        await self._execute_telnet_plain("end", timeout=timeout)
                    except Exception as exc:
                        logger.debug("退出 test-node 时忽略: %s", exc)

            if command.startswith("config-netconf:"):
                await self._enter_config_netconf_view(timeout=timeout)
                output = await self._execute_telnet_plain(command.split(":", 1)[1], timeout=timeout)
                await self._execute_telnet_plain("end", timeout=timeout)
                return output

            if command.startswith("diagnose:"):
                await self._enter_diagnose_view(timeout=timeout)
                via_testnode = self._telnet_diagnose_via_testnode
                try:
                    output = await self._execute_telnet_plain(command.split(":", 1)[1], timeout=timeout)
                    return output
                finally:
                    try:
                        await self._execute_telnet_plain("exit", timeout=timeout)
                    except Exception as exc:
                        logger.debug("退出诊断 shell 时忽略: %s", exc)
                    if via_testnode:
                        try:
                            await self._execute_telnet_plain("exit", timeout=timeout)
                        except Exception as exc:
                            logger.debug("退出 test-node 时忽略: %s", exc)
                    self._telnet_diagnose_via_testnode = False

            await self._ensure_enable_mode(timeout=timeout)
            return await self._execute_telnet_plain(command, timeout=timeout)
        except Exception as e:
            raise CommandExecutionError(f"Telnet 命令执行失败 '{command}': {str(e)}")

    async def _execute_telnet_plain(self, command: str, timeout: int = 10) -> str:
        """执行 Telnet 普通命令并读取输出。"""
        self._telnet_writer.write(f"{command}\r\n")
        await self._telnet_writer.drain()
        output = ""
        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            left = max(1, int(timeout - elapsed))
            chunk = await self._read_until_any(
                patterns=[
                    self._cli_more_marker,
                    self._telnet_prompt_regex,
                    self._bash_diag_marker,
                    self._root_diag_shell_prompt,
                ],
                timeout=left,
            )
            output += chunk
            if self._cli_more_marker.search(chunk):
                # Raisecom 等设备分页常用空格翻页（若无效可再扩展）
                self._telnet_writer.write(" ")
                await self._telnet_writer.drain()
                continue
            break

        output = self._sanitize_cli_pagination(output)
        return self._clean_command_output(output, command)

    async def _read_until_prompt(self, timeout: int = 10) -> str:
        """读取输出直到检测到常见命令提示符。"""
        return await self._read_until_any(
            patterns=[
                self._telnet_prompt_regex,
                self._bash_diag_marker,
                self._root_diag_shell_prompt,
            ],
            timeout=timeout,
        )

    async def _read_until_any(self, patterns: List[Any], timeout: int = 10) -> str:
        """读取输出直到匹配任意模式。"""
        output = ""
        start_time = asyncio.get_event_loop().time()
        while True:
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.warning("Telnet 读取输出超时")
                break

            try:
                chunk = await asyncio.wait_for(self._telnet_reader.read(256), timeout=1)
            except asyncio.TimeoutError:
                continue

            if chunk is None or chunk == "":
                raise ConnectionError("Telnet 连接已由对端关闭（EOF）")

            output += chunk
            for pattern in patterns:
                if hasattr(pattern, "search"):
                    if pattern.search(output):
                        return output
                elif isinstance(pattern, str) and pattern.lower() in output.lower():
                    return output
        return output

    @staticmethod
    def _clean_command_output(output: str, command: str) -> str:
        """清理回显命令和前后空白。"""
        lines = output.replace("\r", "").split("\n")
        cleaned = [line for line in lines if line.strip() and line.strip() != command.strip()]
        return "\n".join(cleaned).strip()

    async def _ensure_enable_mode(self, timeout: int = 10):
        """确保进入特权模式（``<name>#``；未设置 hostname 时 name 为 host）。"""
        self._telnet_writer.write("\r\n")
        await self._telnet_writer.drain()
        prompt_out = await self._read_until_prompt(timeout=3)
        flat = prompt_out.replace("\r", "")
        if self._raisecom_user_exec_prompt.search(flat):
            await self._execute_telnet_plain("enable", timeout=timeout)

    async def _enter_testnode_view(self, timeout: int = 10):
        """进入 test-node 视图。"""
        await self._ensure_enable_mode(timeout=timeout)
        self._telnet_writer.write("testnode\r\n")
        await self._telnet_writer.drain()
        inter = await self._read_until_any(
            patterns=[self._telnet_prompt_regex, "password:"],
            timeout=5,
        )
        if "password" in inter.lower():
            view_pwd = self._password_for_view("testnode")
            if not view_pwd:
                raise ConnectionError("进入 testnode 视图需要密码")
            self._telnet_writer.write(f"{view_pwd}\r\n")
            await self._telnet_writer.drain()
            inter = await self._read_until_any(
                patterns=[self._telnet_prompt_regex],
                timeout=timeout,
            )
        if not re.search(r"\(test-node\)#", inter.replace("\r", "")):
            raise ConnectionError("未成功进入 testnode 视图")

    async def _enter_config_netconf_view(self, timeout: int = 10):
        """进入 netconf 配置视图。"""
        await self._ensure_enable_mode(timeout=timeout)
        await self._execute_telnet_plain("configure terminal", timeout=timeout)
        out = await self._execute_telnet_plain("netconf", timeout=timeout)
        tail = out + await self._read_until_prompt(timeout=3)
        if not re.search(r"\(config-netconf\)#", tail.replace("\r", "")):
            logger.warning("未检测到 config-netconf 提示符，继续尝试执行命令")

    async def _enter_diagnose_view(self, timeout: int = 10):
        """进入诊断 shell。

        Raisecom MSG5200 系列：5200B 在 enable（host#）下使用 ``su``；5200A 使用 ``diagnose``。
        逻辑命令仍统一为 ``diagnose:...`` 前缀，由 ``_active_device_type``（``raisecom_msg5200b`` / ``raisecom_msg5200``）
        与版本指纹（含 ``Product series`` 433/423）决定实际交互命令，避免 5200B 误走 ``diagnose`` 导致无法进入诊断 shell。
        """
        dev = (self._active_device_type or "").strip()
        if dev == "raisecom_msg5200b":
            await self._enter_diagnostic_shell_via_su(timeout=timeout)
            return
        await self._enter_diagnostic_shell_via_diagnose(timeout=timeout)

    async def _enter_diagnostic_shell_via_su(self, timeout: int = 10):
        """5200B：在 host# 执行 ``su``，口令见 ``views.su`` / 登录密码。"""
        await self._ensure_enable_mode(timeout=timeout)
        self._telnet_diagnose_via_testnode = False

        entry_patterns: List[Any] = [
            self._bash_diag_marker,
            self._root_diag_shell_prompt,
            "password:",
            "passwd:",
        ]
        entry_wait = max(20, min(timeout, 60))
        self._telnet_writer.write("su\r\n")
        await self._telnet_writer.drain()
        inter = await self._read_until_any(patterns=entry_patterns, timeout=entry_wait)
        flat = (inter.replace("\r", "") or "").lower()

        if "password" in flat:
            view_pwd = self._password_for_view("su")
            if not view_pwd:
                raise ConnectionError("su 进入诊断 shell 需要口令（views.su 或登录密码）")
            self._telnet_writer.write(f"{view_pwd}\r\n")
            await self._telnet_writer.drain()
            inter = await self._read_until_any(
                patterns=[self._bash_diag_marker, self._root_diag_shell_prompt],
                timeout=entry_wait,
            )

        if not self._diagnostic_shell_prompt_seen(inter):
            tail = (inter.replace("\r", "") or "")[-500:]
            logger.debug("su 入口未识别诊断 shell，输出尾部: %r", tail)
            raise ConnectionError("未成功经 su 进入诊断 shell（未检测到 bash 或 root # 提示符）")

    async def _enter_diagnostic_shell_via_diagnose(self, timeout: int = 10):
        """5200A：在 host# 执行 ``diagnose``；部分固件在 host# 无该命令时需先 test-node 再 diagnose。"""
        await self._ensure_enable_mode(timeout=timeout)
        self._telnet_diagnose_via_testnode = False

        entry_patterns: List[Any] = [
            self._bash_diag_marker,
            self._root_diag_shell_prompt,
            "password:",
            "passwd:",
        ]
        entry_wait = max(20, min(timeout, 60))

        async def _send_diagnose_and_read() -> str:
            self._telnet_writer.write("diagnose\r\n")
            await self._telnet_writer.drain()
            return await self._read_until_any(patterns=entry_patterns, timeout=entry_wait)

        inter = await _send_diagnose_and_read()
        flat = (inter.replace("\r", "") or "").lower()

        if "password" not in flat and not self._diagnostic_shell_prompt_seen(inter):
            if "unknown command" in flat or "% unknown" in flat:
                logger.info("在 host# 下 diagnose 不可用，经 test-node 重试进入诊断 shell")
                await self._enter_testnode_view(timeout=timeout)
                self._telnet_diagnose_via_testnode = True
                inter = await _send_diagnose_and_read()
                flat = (inter.replace("\r", "") or "").lower()

        if "password" in flat:
            view_pwd = self._password_for_view("diagnose")
            if not view_pwd:
                raise ConnectionError("进入 diagnose 视图需要密码")
            self._telnet_writer.write(f"{view_pwd}\r\n")
            await self._telnet_writer.drain()
            inter = await self._read_until_any(
                patterns=[self._bash_diag_marker, self._root_diag_shell_prompt],
                timeout=entry_wait,
            )

        if not self._diagnostic_shell_prompt_seen(inter):
            tail = (inter.replace("\r", "") or "")[-500:]
            logger.debug("diagnose 入口未识别诊断 shell，输出尾部: %r", tail)
            self._telnet_diagnose_via_testnode = False
            raise ConnectionError("未成功进入 diagnose 视图（未检测到 bash 或 root # 提示符）")
    
    async def _detect_device_type(self) -> str:
        """检测设备类型
        
        执行 show version 命令，通过 ConfigParserRegistry 自动检测厂商。
        
        Returns:
            设备类型标识（如 "cisco_sdwan"）
        """
        try:
            merged_parts: List[str] = []
            seen: set[str] = set()
            for command in ("show version", "testnode:show version all", "display version"):
                try:
                    candidate = await self._execute_command(command, timeout=10)
                    if candidate and candidate.strip():
                        key = candidate.strip()
                        if key not in seen:
                            seen.add(key)
                            merged_parts.append(key)
                except Exception as exc:
                    logger.debug("版本探测跳过: %s (%s)", command, exc)
                    continue
            version_output = "\n\n".join(merged_parts)
            if not version_output.strip():
                raise CommandExecutionError("设备版本信息获取失败")
            
            # 尝试所有已注册的解析器
            for vendor in ConfigParserRegistry.list_vendors():
                parser = ConfigParserRegistry.get_parser(vendor)
                if parser and parser.detect_vendor(version_output):
                    logger.info(
                        "自动检测到设备厂商: %s",
                        vendor,
                    )
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
        if device_type in ("raisecom_msg5200", "raisecom_msg5200b"):
            return [
                {"name": "show version", "priority": 1, "optional": False},
                {"name": "testnode:show version all", "priority": 1, "optional": True, "save_as": "show version all"},
                {"name": "show running-config", "priority": 1, "optional": False},
                {"name": "show cpu usage", "priority": 2, "optional": False},
                {"name": "show memory usage", "priority": 2, "optional": False},
                {"name": "show system uptime", "priority": 2, "optional": False},
                {"name": "show dns active", "priority": 2, "optional": True},
                {"name": "config-netconf:show callhome all", "priority": 2, "optional": True, "save_as": "show callhome all"},
                {"name": "show arp", "priority": 2, "optional": True},
                {"name": "show ip route", "priority": 2, "optional": False},
                {"name": "diagnose:ip rule show", "priority": 3, "optional": True},
                {"name": "diagnose:ip route show table 99", "priority": 3, "optional": True},
                {"name": "diagnose:ip route show table 100", "priority": 3, "optional": True},
                {
                    "name": "diagnose:iptables -t mangle -nvL",
                    "priority": 3,
                    "optional": True,
                    "save_as": "diagnose:iptables -t mangle -nvL",
                },
                {"name": "show url-group all security-ip", "priority": 3, "optional": True},
                {"name": "show link detect", "priority": 3, "optional": True},
                {"name": "show interface vlan1", "priority": 3, "optional": True},
                {"name": "show interface ge1", "priority": 3, "optional": True},
            ]
        else:
            logger.warning(f"未知设备类型 '{device_type}'，使用默认命令集")
            return [
                {"name": "show version all", "priority": 1, "optional": False},
                {"name": "show running-config", "priority": 1, "optional": True},
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
                save_as = cmd.get("save_as", cmd_name)
                optional = cmd.get("optional", False)

                if (
                    cmd_name == "diagnose:ip route show table 100"
                    and (self._active_device_type or "") in ("raisecom_msg5200", "raisecom_msg5200b")
                ):
                    rc_out = self._raw_outputs.get("show running-config", "")
                    if self._raisecom_url_group_count(rc_out) <= 1:
                        logger.info(
                            "running-config 中 url-group 不超过 1 个，跳过可选命令 %s",
                            cmd_name,
                        )
                        self._raw_outputs[save_as] = ""
                        continue
                
                try:
                    output = await self._execute_command(cmd_name, timeout=self.config.command_timeout)
                    self._raw_outputs[save_as] = output
                    logger.debug(f"命令 '{cmd_name}' 执行成功（输出长度: {len(output)}）")
                    
                except Exception as e:
                    if optional:
                        logger.warning(f"可选命令 '{cmd_name}' 执行失败，跳过: {e}")
                        self._raw_outputs[save_as] = ""
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

        if command.startswith(("diagnose:", "testnode:", "config-netconf:")):
            raise CommandExecutionError(
                "交互式视图命令（diagnose:/testnode:/config-netconf:）需 Telnet 会话语义，"
                "请使用 --protocol telnet 连接 CPE"
            )

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

    def _persist_collected_artifacts(
        self,
        ctx: FlowContext,
        device_type: str,
        cpe_config: CpeConfiguration,
    ) -> Dict[str, str]:
        """保存原始输出和解析结果到本地文件。"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path("reports") / "deep_dive_raw" / f"{ctx.trace_id}_{ts}"
        out_dir.mkdir(parents=True, exist_ok=True)

        raw_text_path = out_dir / "raw_outputs.txt"
        raw_json_path = out_dir / "raw_outputs.json"
        parsed_json_path = out_dir / "parsed_cpe_config.json"

        raw_text_sections = []
        for cmd_name, output in self._raw_outputs.items():
            raw_text_sections.append(f"===== {cmd_name} =====\n{output}\n")
        raw_text_path.write_text("\n".join(raw_text_sections), encoding="utf-8")
        raw_json_path.write_text(json.dumps(self._raw_outputs, ensure_ascii=False, indent=2), encoding="utf-8")

        parsed_payload = {
            "device_type": device_type,
            "vendor": cpe_config.vendor,
            "model": cpe_config.model,
            "version": cpe_config.version,
            "hostname": cpe_config.hostname,
            "interfaces": [iface.to_json_dict() for iface in cpe_config.interfaces],
            "routes": [route.to_json_dict() for route in cpe_config.routes],
            "sdwan_policies": [policy.to_json_dict() for policy in cpe_config.sdwan_policies],
            "vpn_tunnels": [tunnel.to_json_dict() for tunnel in cpe_config.vpn_tunnels],
            "nat_rules": [rule.to_json_dict() for rule in cpe_config.nat_rules],
        }
        parsed_json_path.write_text(json.dumps(parsed_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "raw_text": str(raw_text_path),
            "raw_json": str(raw_json_path),
            "parsed_json": str(parsed_json_path),
        }
    
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
