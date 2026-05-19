"""
CPE 采集器单元测试

测试 CpeCollector 的各项功能。
遵循 SDWAN_SPEC.md §2.4 工具系统规范
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.services.collector.cpe_collector import (
    CpeCollector,
    CpeCollectorConfig,
    CommandExecutionError,
)
from sdwan_desktop.services.parser.vendor import ConfigParserRegistry
from sdwan_desktop.services.parser.vendor.cisco_sdwan import CiscoSdwanParser


@pytest.fixture
def valid_config():
    """创建有效的 CPE 采集器配置"""
    return CpeCollectorConfig(
        host="192.168.1.1",
        port=22,
        username="admin",
        password="password123",
        protocol="ssh",
        command_timeout=10,
        connect_timeout=30,
    )


@pytest.fixture
def collector(valid_config):
    """创建 CPE 采集器实例"""
    return CpeCollector(config=valid_config)


class TestCpeCollectorConfig:
    """CPE 采集器配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = CpeCollectorConfig()
        assert config.host == ""
        assert config.port == 22
        assert config.username == ""
        assert config.password is None
        assert config.protocol == "ssh"
        assert config.command_timeout == 10
        assert config.connect_timeout == 30
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = CpeCollectorConfig(
            host="10.0.0.1",
            port=2222,
            username="test",
            password="secret",
        )
        assert config.host == "10.0.0.1"
        assert config.port == 2222
        assert config.username == "test"
        assert config.password == "secret"


class TestViewPasswordResolution:
    """二次视图口令：设备级、通用文件、登录密码合并顺序。"""

    def test_testnode_device_over_global_over_login(self) -> None:
        cfg = CpeCollectorConfig(
            password="L",
            testnode_password="D",
            preset_view_passwords={"testnode": "G"},
        )
        col = CpeCollector(cfg)
        assert col._password_for_view("testnode") == "D"

        cfg2 = CpeCollectorConfig(password="L", preset_view_passwords={"testnode": "G"})
        assert CpeCollector(cfg2)._password_for_view("testnode") == "G"

        cfg3 = CpeCollectorConfig(password="L")
        assert CpeCollector(cfg3)._password_for_view("testnode") == "L"

    def test_diagnose_preset_then_testnode_chain(self) -> None:
        cfg = CpeCollectorConfig(
            password="L",
            preset_view_passwords={"diagnose": "D", "testnode": "T"},
        )
        assert CpeCollector(cfg)._password_for_view("diagnose") == "D"

        cfg2 = CpeCollectorConfig(password="L", preset_view_passwords={"testnode": "T"})
        assert CpeCollector(cfg2)._password_for_view("diagnose") == "T"

        cfg3 = CpeCollectorConfig(password="L", testnode_password="X")
        assert CpeCollector(cfg3)._password_for_view("diagnose") == "X"

    def test_default_config_has_empty_preset_map(self) -> None:
        cfg = CpeCollectorConfig()
        assert cfg.preset_view_passwords == {}


class TestCpeCollectorDiagnosticShellPrompt:
    """诊断 shell 提示符识别（5200B su 后 busybox root ``#``）。"""

    def test_diagnostic_shell_prompt_seen_bash(self) -> None:
        col = CpeCollector(
            CpeCollectorConfig(host="1.1.1.1", username="u", password="p", protocol="telnet")
        )
        assert col._diagnostic_shell_prompt_seen("entering shell\nbash-4.4# ")

    def test_diagnostic_shell_prompt_seen_root_hash(self) -> None:
        col = CpeCollector(
            CpeCollectorConfig(host="1.1.1.1", username="u", password="p", protocol="telnet")
        )
        assert col._diagnostic_shell_prompt_seen("Password:\r\n\r\n# ")
        assert col._diagnostic_shell_prompt_seen("x\n#")

    def test_diagnostic_shell_prompt_not_host_cli(self) -> None:
        col = CpeCollector(
            CpeCollectorConfig(host="1.1.1.1", username="u", password="p", protocol="telnet")
        )
        assert not col._diagnostic_shell_prompt_seen("show ver\nhost# ")


class TestCpeCollectorPaginationAndRaisecom:
    """分页清理与 Raisecom url-group 计数。"""

    def test_sanitize_cli_pagination_inline_more(self) -> None:
        raw = (
            "tunnel tunnel1_5 \n"
            "--More-- (14% of 3355 bytes)                             type vxlan source-id soft interval 10\n"
            " peer 5.0.1.1\n"
        )
        out = CpeCollector._sanitize_cli_pagination(raw)
        assert "--More--" not in out
        assert "type vxlan source-id soft interval 10" in out
        assert "tunnel tunnel1_5" in out

    def test_raisecom_url_group_count(self) -> None:
        cfg = "!config\nurl-group a\nexit\nurl-group b\nexit\n"
        assert CpeCollector._raisecom_url_group_count(cfg) == 2
        assert CpeCollector._raisecom_url_group_count("no url-group") == 0


class TestCpeCollectorTelnetRciOsPrompt:
    """RCIOS Telnet 行尾提示符：须同时识别默认 host 与自定义 hostname。"""

    def test_telnet_prompt_regex_host_and_custom_name(self) -> None:
        cfg = CpeCollectorConfig(host="1.1.1.1", username="u", password="p", protocol="telnet")
        col = CpeCollector(cfg)
        assert col._telnet_prompt_regex.search("x\nhost# ")
        assert col._telnet_prompt_regex.search("x\nhost> ")
        assert col._telnet_prompt_regex.search("x\ncpe-name# ")
        assert col._telnet_prompt_regex.search("x\ncpe-name(test-node)# ")
        assert col._telnet_prompt_regex.search("x\nbash-4.3# ")

    def test_raisecom_user_exec_prompt(self) -> None:
        cfg = CpeCollectorConfig(host="1.1.1.1", username="u", password="p", protocol="telnet")
        col = CpeCollector(cfg)
        assert col._raisecom_user_exec_prompt.search("banner\ncpe-name> ")
        assert col._raisecom_user_exec_prompt.search("host> ")


class TestCpeCollectorValidation:
    """CPE 采集器配置验证测试"""
    
    @pytest.mark.asyncio
    async def test_validate_valid_config(self, collector):
        """测试有效配置验证"""
        ctx = FlowContext(flow_id="test-001")
        result = await collector.validate(ctx)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_missing_host(self):
        """测试缺少主机地址"""
        config = CpeCollectorConfig(username="admin", password="pass")
        collector = CpeCollector(config=config)
        ctx = FlowContext(flow_id="test-001")
        result = await collector.validate(ctx)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_missing_username(self):
        """测试缺少用户名"""
        config = CpeCollectorConfig(host="192.168.1.1", password="pass")
        collector = CpeCollector(config=config)
        ctx = FlowContext(flow_id="test-001")
        result = await collector.validate(ctx)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_missing_password(self):
        """测试缺少密码（SSH 协议）"""
        config = CpeCollectorConfig(host="192.168.1.1", username="admin")
        collector = CpeCollector(config=config)
        ctx = FlowContext(flow_id="test-001")
        result = await collector.validate(ctx)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_invalid_protocol(self):
        """测试无效协议"""
        config = CpeCollectorConfig(
            host="192.168.1.1",
            username="admin",
            password="pass",
            protocol="ftp",
        )
        collector = CpeCollector(config=config)
        ctx = FlowContext(flow_id="test-001")
        result = await collector.validate(ctx)
        assert result is False


class TestCpeCollectorConnection:
    """CPE 采集器连接测试"""
    
    @pytest.mark.asyncio
    async def test_connect_ssh_success(self, collector):
        """测试 SSH 连接成功"""
        with patch('paramiko.SSHClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            await collector._connect_ssh()
            
            assert collector._client is not None
            assert collector._connection_id == "192.168.1.1:22:admin"
            mock_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_ssh_auth_failure(self, collector):
        """测试 SSH 认证失败"""
        import paramiko
        
        with patch('paramiko.SSHClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.connect.side_effect = paramiko.AuthenticationException("Auth failed")
            
            with pytest.raises(ConnectionError, match="SSH 认证失败"):
                await collector._connect_ssh()
    
    @pytest.mark.asyncio
    async def test_connect_ssh_connection_failure(self, collector):
        """测试 SSH 连接失败"""
        import paramiko
        
        with patch('paramiko.SSHClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.connect.side_effect = paramiko.SSHException("Connection refused")
            
            with pytest.raises(ConnectionError, match="SSH 连接失败"):
                await collector._connect_ssh()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, collector):
        """测试断开连接"""
        mock_client = MagicMock()
        collector._client = mock_client
        collector._connection_id = "192.168.1.1:22:admin"
        
        await collector._disconnect()
        
        assert collector._client is None
        assert collector._connection_id is None
        mock_client.close.assert_called_once()


class TestCpeCollectorDeviceDetection:
    """设备类型检测测试"""
    
    @pytest.mark.asyncio
    async def test_detect_cisco_sdwan(self, collector):
        """测试检测 Cisco SD-WAN 设备"""
        # 注册 Cisco SD-WAN 解析器
        ConfigParserRegistry.clear_all()
        ConfigParserRegistry.register(CiscoSdwanParser())
        
        # Mock 命令执行
        collector._execute_command = AsyncMock(
            return_value="Viptela VEDGE-1000 Software (vedge)\nVersion 20.9.3"
        )
        
        device_type = await collector._detect_device_type()
        
        assert device_type == "cisco_sdwan"
    
    @pytest.mark.asyncio
    async def test_detect_unknown_device(self, collector):
        """测试检测未知设备"""
        ConfigParserRegistry.clear_all()
        
        collector._execute_command = AsyncMock(return_value="Unknown device output")
        
        device_type = await collector._detect_device_type()
        
        assert device_type == "generic"
    
    @pytest.mark.asyncio
    async def test_detect_failure(self, collector):
        """检测设备类型检测失败"""
        collector._execute_command = AsyncMock(side_effect=Exception("Command failed"))
        
        device_type = await collector._detect_device_type()
        
        assert device_type == "generic"


class TestCpeCollectorCommandExecution:
    """命令执行测试"""
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self, collector):
        """测试命令执行成功"""
        mock_client = MagicMock()
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        
        mock_stdout.read.return_value = b"show version output\nVersion 20.9.3"
        mock_stderr.read.return_value = b""
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        collector._client = mock_client
        
        output = await collector._execute_command("show version", timeout=10)
        
        assert "Version 20.9.3" in output
        mock_client.exec_command.assert_called_once_with("show version", timeout=10)
    
    @pytest.mark.asyncio
    async def test_execute_command_no_connection(self, collector):
        """测试无连接时执行命令"""
        with pytest.raises(ConnectionError, match="未建立连接"):
            await collector._execute_command("show version")
    
    @pytest.mark.asyncio
    async def test_execute_command_failure(self, collector):
        """测试命令执行失败"""
        mock_client = MagicMock()
        mock_client.exec_command.side_effect = Exception("Command timeout")
        collector._client = mock_client
        
        with pytest.raises(CommandExecutionError, match="命令执行失败"):
            await collector._execute_command("show version")


class TestCpeCollectorCommandTemplate:
    """命令模板加载测试"""
    
    def test_load_cisco_sdwan_commands(self, collector):
        """测试加载 Cisco SD-WAN 命令模板"""
        commands = collector._load_command_template("cisco_sdwan")
        
        assert len(commands) > 0
        assert any(cmd["name"] == "show version" for cmd in commands)
        assert any(cmd["name"] == "show interface" for cmd in commands)
        assert any(cmd["name"] == "show ip route" for cmd in commands)
    
    def test_load_unknown_device_commands(self, collector):
        """测试加载未知设备命令模板"""
        commands = collector._load_command_template("unknown_vendor")
        
        assert len(commands) > 0
        assert any(cmd["name"] == "show version" for cmd in commands)


class TestCpeCollectorExecuteCommands:
    """批量命令执行测试"""
    
    @pytest.mark.asyncio
    async def test_execute_commands_all_success(self, collector):
        """测试所有命令执行成功"""
        commands = [
            {"name": "show version", "priority": 1, "optional": False},
            {"name": "show interface", "priority": 2, "optional": False},
        ]
        
        collector._execute_command = AsyncMock(return_value="command output")
        
        await collector._execute_commands(commands)
        
        assert len(collector._raw_outputs) == 2
        assert "show version" in collector._raw_outputs
        assert "show interface" in collector._raw_outputs
    
    @pytest.mark.asyncio
    async def test_execute_commands_optional_failure(self, collector):
        """测试可选命令失败不影响整体"""
        commands = [
            {"name": "show version", "priority": 1, "optional": False},
            {"name": "show policy", "priority": 2, "optional": True},
        ]
        
        def side_effect(cmd, **kwargs):
            if cmd == "show policy":
                raise Exception("Policy command failed")
            return "success"
        
        collector._execute_command = AsyncMock(side_effect=side_effect)
        
        await collector._execute_commands(commands)
        
        assert len(collector._raw_outputs) == 2
        assert collector._raw_outputs["show version"] == "success"
        assert collector._raw_outputs["show policy"] == ""
    
    @pytest.mark.asyncio
    async def test_execute_commands_required_failure(self, collector):
        """测试必需命令失败抛出异常"""
        commands = [
            {"name": "show version", "priority": 1, "optional": False},
        ]
        
        collector._execute_command = AsyncMock(side_effect=Exception("Required command failed"))
        
        with pytest.raises(Exception, match="Required command failed"):
            await collector._execute_commands(commands)


class TestCpeCollectorFullCollection:
    """完整采集流程测试"""
    
    @pytest.mark.asyncio
    async def test_collect_success(self, collector):
        """测试完整采集流程成功"""
        # 注册 Cisco SD-WAN 解析器
        ConfigParserRegistry.clear_all()
        ConfigParserRegistry.register(CiscoSdwanParser())
        
        ctx = FlowContext(flow_id="test-001")
        
        # Mock 所有方法
        collector.validate = AsyncMock(return_value=True)
        collector._connect = AsyncMock()
        collector._detect_device_type = AsyncMock(return_value="cisco_sdwan")
        collector._execute_commands = AsyncMock()
        collector._disconnect = AsyncMock()
        
        # Mock 原始输出
        collector._raw_outputs = {
            "show version": "Viptela VEDGE-1000 Software (vedge)\nVersion 20.9.3",
            "show interface": "",
            "show ip route": "",
        }
        
        result = await collector.collect(ctx)
        
        assert result.success is True
        assert "cpe_configuration" in result.data
        assert result.data["cpe_configuration"].vendor == "cisco_sdwan"
        assert len(result.collected_items) > 0
    
    @pytest.mark.asyncio
    async def test_collect_validation_failure(self, collector):
        """测试配置验证失败"""
        ctx = FlowContext(flow_id="test-001")
        
        collector.validate = AsyncMock(return_value=False)
        
        result = await collector.collect(ctx)
        
        assert result.success is False
        assert "配置无效" in result.error_message
    
    @pytest.mark.asyncio
    async def test_collect_exception_handling(self, collector):
        """测试异常处理"""
        ctx = FlowContext(flow_id="test-001")
        
        collector.validate = AsyncMock(return_value=True)
        collector._connect = AsyncMock(side_effect=Exception("Connection failed"))
        collector._disconnect = AsyncMock()
        
        result = await collector.collect(ctx)
        
        assert result.success is False
        assert "采集失败" in result.error_message


class TestCpeCollectorTelnetRead:
    """Telnet 读循环：EOF 须立即失败，避免空转直至总超时。"""

    @pytest.mark.asyncio
    async def test_read_until_any_eof_raises(self) -> None:
        cfg = CpeCollectorConfig(
            host="10.0.0.1",
            port=23,
            username="u",
            password="p",
            protocol="telnet",
        )
        col = CpeCollector(cfg)
        mock_reader = MagicMock()
        mock_reader.read = AsyncMock(return_value="")
        col._telnet_reader = mock_reader
        with pytest.raises(ConnectionError, match="EOF"):
            await col._read_until_any([col._telnet_prompt_regex], timeout=5)


class TestCpeCollectorSupportedItems:
    """支持采集项目测试"""
    
    def teardown_method(self):
        """测试清理"""
        ConfigParserRegistry.clear_all()
    
    def test_get_supported_items(self, collector):
        """测试获取支持的采集项目"""
        items = collector.get_supported_items()
        
        assert isinstance(items, list)
        assert "version" in items
        assert "interfaces" in items
        assert "routes" in items
        assert "sdwan_policies" in items
        assert "vpn_tunnels" in items
        assert "nat_rules" in items
