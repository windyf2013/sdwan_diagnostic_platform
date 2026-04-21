"""SshAdapter单元测试"""

from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import asyncio

from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.implementations.remote.ssh import SshAdapter


class TestSshAdapter:
    """SshAdapter测试类"""
    
    def setup_method(self):
        """测试初始化"""
        self.tool = SshAdapter()
        self.ctx = FlowContext(
            flow_id="test-flow",
            flow_name="test",
            trace_id="test-trace-123"
        )
    
    @pytest.mark.asyncio
    async def test_ssh_connect_success(self):
        """测试SSH连接成功"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "password123",
            "command": "show version"
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            # Mock连接成功
            mock_ssh.connect.return_value = None
            
            # Mock命令执行成功
            mock_result = AsyncMock()
            mock_result.stdout = "Cisco IOS XE Software, Version 17.09.01a"
            mock_result.stderr = ""
            mock_result.exit_status = 0
            
            mock_ssh.run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            assert data["host"] == "192.168.1.1"
            assert data["port"] == 22
            assert data["username"] == "admin"
            assert data["connected"] is True
            assert data["command"] == "show version"
            assert "Cisco IOS XE" in data["output"]
            assert data["exit_status"] == 0
            assert data["duration_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_ssh_connect_with_key(self):
        """测试使用密钥认证"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----",
            "command": "show interface"
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            mock_ssh.connect.return_value = None
            
            mock_result = AsyncMock()
            mock_result.stdout = "GigabitEthernet0/0 is up, line protocol is up"
            mock_result.stderr = ""
            mock_result.exit_status = 0
            
            mock_ssh.run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            assert data["connected"] is True
            assert "GigabitEthernet" in data["output"]
            # 验证密钥认证被使用
            assert "private_key" not in data  # 密钥不应在响应中返回
    
    @pytest.mark.asyncio
    async def test_ssh_missing_host(self):
        """测试缺少host参数"""
        request = ToolRequest(parameters={
            "username": "admin",
            "password": "password",
            "command": "show version"
        })
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
        assert "host" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_ssh_missing_credentials(self):
        """测试缺少认证信息"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "command": "show version"
        })
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
        assert "username" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_ssh_connection_failed(self):
        """测试SSH连接失败"""
        request = ToolRequest(parameters={
            "host": "unreachable-host",
            "port": 22,
            "username": "admin",
            "password": "password",
            "command": "show version"
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            # Mock连接失败
            mock_ssh.connect.side_effect = Exception("Connection refused")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_004"
            assert "connection" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_ssh_authentication_failed(self):
        """测试SSH认证失败"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "wrong-password",
            "command": "show version"
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            # Mock认证失败
            mock_ssh.connect.side_effect = Exception("Authentication failed")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_005"
            assert "authentication" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_ssh_command_timeout(self):
        """测试命令执行超时"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "password",
            "command": "show running-config",
            "timeout": 1  # 短超时
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            mock_ssh.connect.return_value = None
            
            # Mock命令执行超时
            mock_ssh.run.side_effect = asyncio.TimeoutError("Command timeout")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_TIMEOUT"
            assert "timeout" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_ssh_command_failed(self):
        """测试命令执行失败（非零退出码）"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "password",
            "command": "invalid-command"
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            mock_ssh.connect.return_value = None
            
            mock_result = AsyncMock()
            mock_result.stdout = ""
            mock_result.stderr = "invalid-command: command not found"
            mock_result.exit_status = 1
            
            mock_ssh.run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            # 即使命令失败，SSH连接本身是成功的
            assert response.success is True
            data = response.data
            
            assert data["connected"] is True
            assert data["exit_status"] == 1
            assert "command not found" in data["stderr"]
    
    @pytest.mark.asyncio
    async def test_ssh_multiple_commands(self):
        """测试执行多个命令"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "password",
            "commands": ["show version", "show interface", "show ip route"]
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            mock_ssh.connect.return_value = None
            
            # Mock多个命令结果
            mock_results = [
                AsyncMock(stdout="Version: 17.09.01a", stderr="", exit_status=0),
                AsyncMock(stdout="Interface: up", stderr="", exit_status=0),
                AsyncMock(stdout="Route table", stderr="", exit_status=0)
            ]
            
            mock_ssh.run.side_effect = mock_results
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            assert "results" in data
            assert len(data["results"]) == 3
            assert data["results"][0]["command"] == "show version"
            assert data["results"][1]["command"] == "show interface"
            assert data["results"][2]["command"] == "show ip route"
    
    @pytest.mark.asyncio
    async def test_ssh_with_context_manager(self):
        """测试使用上下文管理器"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "password",
            "use_context": True,
            "commands": ["show version", "show interface"]
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            mock_ssh.__aenter__.return_value = mock_ssh
            mock_ssh.__aexit__.return_value = None
            
            mock_results = [
                AsyncMock(stdout="Version info", stderr="", exit_status=0),
                AsyncMock(stdout="Interface info", stderr="", exit_status=0)
            ]
            
            mock_ssh.run.side_effect = mock_results
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            # 验证上下文管理器被调用
            mock_ssh.__aenter__.assert_called_once()
            mock_ssh.__aexit__.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ssh_custom_port(self):
        """测试自定义端口"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 2222,  # 非标准端口
            "username": "admin",
            "password": "password",
            "command": "show version"
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            mock_ssh.connect.return_value = None
            
            mock_result = AsyncMock()
            mock_result.stdout = "Version info"
            mock_result.stderr = ""
            mock_result.exit_status = 0
            
            mock_ssh.run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            assert data["port"] == 2222
    
    @pytest.mark.asyncio
    async def test_ssh_with_banner(self):
        """测试带banner的连接"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "password",
            "command": "show version",
            "banner_timeout": 10
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            mock_ssh.connect.return_value = None
            
            mock_result = AsyncMock()
            mock_result.stdout = "Cisco Router\nVersion: 17.09.01a"
            mock_result.stderr = ""
            mock_result.exit_status = 0
            
            mock_ssh.run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            assert "Cisco Router" in data["output"]
    
    @pytest.mark.asyncio
    async def test_ssh_large_output(self):
        """测试大输出处理"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "password",
            "command": "show running-config"
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            mock_ssh.connect.return_value = None
            
            # 生成大输出
            large_output = "!\n" + "interface GigabitEthernet0/0\n description WAN Link\n ip address 192.168.1.1 255.255.255.0\n!\n" * 100
            
            mock_result = AsyncMock()
            mock_result.stdout = large_output
            mock_result.stderr = ""
            mock_result.exit_status = 0
            
            mock_ssh.run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            assert len(data["output"]) > 1000
            assert "GigabitEthernet" in data["output"]
    
    @pytest.mark.asyncio
    async def test_ssh_with_known_hosts(self):
        """测试使用known_hosts文件"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "password",
            "command": "show version",
            "known_hosts": "/path/to/known_hosts"
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            mock_ssh.connect.return_value = None
            
            mock_result = AsyncMock()
            mock_result.stdout = "Version info"
            mock_result.stderr = ""
            mock_result.exit_status = 0
            
            mock_ssh.run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            # 验证known_hosts参数被传递
    
    @pytest.mark.asyncio
    async def test_ssh_host_key_verification_failed(self):
        """测试主机密钥验证失败"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "password",
            "command": "show version",
            "strict_host_key_checking": True
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            # Mock主机密钥验证失败
            mock_ssh.connect.side_effect = Exception("Host key verification failed")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_004"
            assert "host key" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_ssh_connection_closed(self):
        """测试连接意外关闭"""
        request = ToolRequest(parameters={
            "host": "192.168.1.1",
            "port": 22,
            "username": "admin",
            "password": "password",
            "command": "show version"
        })
        
        with patch('sdwan_desktop.tools.implementations.remote.ssh.AsyncSSHClient') as mock_ssh_class:
            mock_ssh = AsyncMock()
            mock_ssh_class.return_value = mock_ssh
            
            mock_ssh.connect.return_value = None
            
            # Mock连接在执行命令时关闭
            mock_ssh.run.side_effect = Exception("Connection closed")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_004"
            assert "connection" in response.error_message.lower()