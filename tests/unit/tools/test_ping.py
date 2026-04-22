"""PingTool单元测试"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.implementations.network.ping import PingTool


class TestPingTool:
    """PingTool测试类"""
    
    def setup_method(self):
        """测试初始化"""
        self.tool = PingTool()
        self.ctx = FlowContext(
            flow_id="test-flow",
            flow_name="test",
            trace_id="test-trace-123"
        )
    
    @pytest.mark.asyncio
    async def test_ping_success(self):
        """测试Ping成功场景"""
        # 准备请求
        request = ToolRequest(
            tool_name="ping",
            parameters={
                "host": "127.0.0.1",
                "count": 2,
                "timeout": 1,
                "packet_size": 56
            }
        )
        
        # Mock asyncio.create_subprocess_exec
        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            # 模拟异步进程
            mock_process = AsyncMock()
            mock_process.returncode = 0
            
            # 模拟communicate方法返回
            mock_process.communicate = AsyncMock(return_value=(
                b"""
Pinging 127.0.0.1 with 56 bytes of data:
Reply from 127.0.0.1: bytes=56 time=1ms TTL=128
Reply from 127.0.0.1: bytes=56 time=2ms TTL=128

Ping statistics for 127.0.0.1:
    Packets: Sent = 2, Received = 2, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 1ms, Maximum = 2ms, Average = 1.5ms
""",
                b""
            ))
            
            mock_create_subprocess.return_value = mock_process
            
            # 执行测试
            response = await self.tool.execute(request, self.ctx)
            
            # 验证结果
            assert response.success is True
            assert response.trace_id == "test-trace-123"
            assert "rtt_min" in response.data
            assert "rtt_avg" in response.data
            assert "rtt_max" in response.data
            assert "loss_rate" in response.data
            assert response.data["loss_rate"] == 0.0
            assert response.data["rtt_min"] == 1.0
            assert response.data["rtt_avg"] == 1.5
            assert response.data["rtt_max"] == 2.0
    
    @pytest.mark.asyncio
    async def test_ping_missing_host(self):
        """测试缺少host参数"""
        request = ToolRequest(
            tool_name="ping",
            parameters={}
        )
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
        assert "缺少必填参数" in response.error_message
    
    @pytest.mark.asyncio
    async def test_ping_timeout(self):
        """测试Ping超时"""
        request = ToolRequest(
            tool_name="ping",
            parameters={"host": "192.0.2.1", "timeout": 1}
        )
        
        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            # 模拟超时
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError("Command timed out"))
            
            mock_create_subprocess.return_value = mock_process
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_TIMEOUT"
    
    @pytest.mark.asyncio
    async def test_ping_partial_loss(self):
        """测试部分丢包"""
        request = ToolRequest(tool_name="ping", parameters={"host": "127.0.0.1", "count": 4})
        
        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            # 模拟异步进程
            mock_process = AsyncMock()
            mock_process.returncode = 0
            
            # 模拟communicate方法返回
            mock_process.communicate = AsyncMock(return_value=(
                b"""
Pinging 127.0.0.1 with 56 bytes of data:
Reply from 127.0.0.1: bytes=56 time=10ms TTL=128
Request timed out.
Reply from 127.0.0.1: bytes=56 time=12ms TTL=128
Request timed out.

Ping statistics for 127.0.0.1:
    Packets: Sent = 4, Received = 2, Lost = 2 (50% loss),
Approximate round trip times in milli-seconds:
    Minimum = 10ms, Maximum = 12ms, Average = 11ms
""",
                b""
            ))
            
            mock_create_subprocess.return_value = mock_process
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            assert response.data["loss_rate"] == 0.5
            assert response.data["rtt_min"] == 10.0
            assert response.data["rtt_avg"] == 11.0
            assert response.data["rtt_max"] == 12.0
    
    @pytest.mark.asyncio
    async def test_ping_windows_chinese_output(self):
        """测试Windows中文输出解析"""
        request = ToolRequest(tool_name="ping", parameters={"host": "127.0.0.1"})
        
        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            # 模拟异步进程
            mock_process = AsyncMock()
            mock_process.returncode = 0
            
            # 模拟communicate方法返回
            mock_process.communicate = AsyncMock(return_value=(
                """
正在 Ping 127.0.0.1 具有 56 字节的数据:
来自 127.0.0.1 的回复: 字节=56 时间=1ms TTL=128
来自 127.0.0.1 的回复: 字节=56 时间=2ms TTL=128

127.0.0.1 的 Ping 统计信息:
    数据包: 已发送 = 2，已接收 = 2，丢失 = 0 (0% 丢失)，
往返行程的估计时间(以毫秒为单位):
    最短 = 1ms，最长 = 2ms，平均 = 1.5ms
""".encode('utf-8'),
                b""
            ))
            
            mock_create_subprocess.return_value = mock_process
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            assert response.data["loss_rate"] == 0.0
            assert response.data["rtt_min"] == 1.0
            assert response.data["rtt_avg"] == 1.5
            assert response.data["rtt_max"] == 2.0
    
    @pytest.mark.asyncio
    async def test_ping_invalid_host(self):
        """测试无效主机名"""
        request = ToolRequest(tool_name="ping", parameters={"host": "invalid-hostname"})
        
        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            # 模拟异步进程
            mock_process = AsyncMock()
            mock_process.returncode = 1
            
            # 模拟communicate方法返回
            mock_process.communicate = AsyncMock(return_value=(
                b"Ping request could not find host invalid-hostname.",
                b""
            ))
            
            mock_create_subprocess.return_value = mock_process
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_002"
