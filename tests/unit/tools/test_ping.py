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
            parameters={
                "host": "127.0.0.1",
                "count": 2,
                "timeout": 1,
                "packet_size": 56
            }
        )
        
        # Mock subprocess调用
        with patch('subprocess.run') as mock_run:
            # 模拟ping成功输出
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = """
Pinging 127.0.0.1 with 56 bytes of data:
Reply from 127.0.0.1: bytes=56 time<1ms TTL=128
Reply from 127.0.0.1: bytes=56 time<1ms TTL=128

Ping statistics for 127.0.0.1:
    Packets: Sent = 2, Received = 2, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 0ms, Maximum = 0ms, Average = 0ms
"""
            mock_run.return_value = mock_result
            
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
    
    @pytest.mark.asyncio
    async def test_ping_missing_host(self):
        """测试缺少host参数"""
        request = ToolRequest(parameters={})
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
        assert "缺少必填参数" in response.error_message
    
    @pytest.mark.asyncio
    async def test_ping_timeout(self):
        """测试Ping超时"""
        request = ToolRequest(parameters={"host": "192.0.2.1", "timeout": 1})
        
        with patch('subprocess.run') as mock_run:
            # 模拟超时
            mock_run.side_effect = TimeoutError("Command timed out")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_TIMEOUT"
    
    @pytest.mark.asyncio
    async def test_ping_partial_loss(self):
        """测试部分丢包"""
        request = ToolRequest(parameters={"host": "127.0.0.1", "count": 4})
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = """
Pinging 127.0.0.1 with 56 bytes of data:
Reply from 127.0.0.1: bytes=56 time=10ms TTL=128
Request timed out.
Reply from 127.0.0.1: bytes=56 time=12ms TTL=128
Request timed out.

Ping statistics for 127.0.0.1:
    Packets: Sent = 4, Received = 2, Lost = 2 (50% loss),
Approximate round trip times in milli-seconds:
    Minimum = 10ms, Maximum = 12ms, Average = 11ms
"""
            mock_run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            assert response.data["loss_rate"] == 0.5
            assert response.data["rtt_min"] == 10.0
            assert response.data["rtt_avg"] == 11.0
            assert response.data["rtt_max"] == 12.0
    
    @pytest.mark.asyncio
    async def test_ping_windows_chinese_output(self):
        """测试Windows中文输出解析"""
        request = ToolRequest(parameters={"host": "127.0.0.1"})
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = """
正在 Ping 127.0.0.1 具有 56 字节的数据:
来自 127.0.0.1 的回复: 字节=56 时间<1ms TTL=128
来自 127.0.0.1 的回复: 字节=56 时间<1ms TTL=128

127.0.0.1 的 Ping 统计信息:
    数据包: 已发送 = 2，已接收 = 2，丢失 = 0 (0% 丢失)，
往返行程的估计时间(以毫秒为单位):
    最短 = 0ms，最长 = 0ms，平均 = 0ms
"""
            mock_run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            assert response.data["loss_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_ping_invalid_host(self):
        """测试无效主机名"""
        request = ToolRequest(parameters={"host": "invalid-hostname"})
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = "Ping request could not find host invalid-hostname."
            mock_run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_002"