"""TcpPortTool单元测试"""

from unittest.mock import MagicMock, patch
import pytest
import asyncio

from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.implementations.network.tcping import TcpPortTool


class TestTcpPortTool:
    """TcpPortTool测试类"""
    
    def setup_method(self):
        """测试初始化"""
        self.tool = TcpPortTool()
        self.ctx = FlowContext(
            flow_id="test-flow",
            flow_name="test",
            trace_id="test-trace-123"
        )
    
    @pytest.mark.asyncio
    async def test_tcping_success(self):
        """测试TCP端口连接成功"""
        request = ToolRequest(parameters={
            "host": "example.com",
            "port": 80,
            "timeout": 5
        })
        
        with patch('asyncio.open_connection') as mock_open_connection:
            mock_reader = MagicMock()
            mock_writer = MagicMock()
            mock_open_connection.return_value = (mock_reader, mock_writer)
            
            # Mock时间测量
            with patch('time.perf_counter') as mock_time:
                mock_time.side_effect = [0.0, 0.15]  # 150ms延迟
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert response.data["port_open"] is True
                assert response.data["response_time_ms"] == 150.0
                assert response.data["host"] == "example.com"
                assert response.data["port"] == 80
                
                # 验证连接被正确关闭
                mock_writer.close.assert_called_once()
                mock_writer.wait_closed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_tcping_missing_host(self):
        """测试缺少host参数"""
        request = ToolRequest(parameters={"port": 80})
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
    
    @pytest.mark.asyncio
    async def test_tcping_missing_port(self):
        """测试缺少port参数"""
        request = ToolRequest(parameters={"host": "example.com"})
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
    
    @pytest.mark.asyncio
    async def test_tcping_connection_refused(self):
        """测试连接被拒绝"""
        request = ToolRequest(parameters={
            "host": "localhost",
            "port": 9999
        })
        
        with patch('asyncio.open_connection') as mock_open_connection:
            mock_open_connection.side_effect = ConnectionRefusedError("Connection refused")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True  # 连接被拒绝也是一种有效结果
            assert response.data["port_open"] is False
            assert "Connection refused" in response.data["error_message"]
    
    @pytest.mark.asyncio
    async def test_tcping_timeout(self):
        """测试连接超时"""
        request = ToolRequest(parameters={
            "host": "slow-host.com",
            "port": 80,
            "timeout": 1
        })
        
        with patch('asyncio.open_connection') as mock_open_connection:
            mock_open_connection.side_effect = asyncio.TimeoutError("Connection timeout")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True  # 超时也是一种有效结果
            assert response.data["port_open"] is False
            assert "timeout" in response.data["error_message"].lower()
    
    @pytest.mark.asyncio
    async def test_tcping_network_unreachable(self):
        """测试网络不可达"""
        request = ToolRequest(parameters={
            "host": "unreachable-host.local",
            "port": 443
        })
        
        with patch('asyncio.open_connection') as mock_open_connection:
            mock_open_connection.side_effect = OSError("Network is unreachable")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True  # 网络不可达也是一种有效结果
            assert response.data["port_open"] is False
            assert "unreachable" in response.data["error_message"].lower()
    
    @pytest.mark.asyncio
    async def test_tcping_ipv6_address(self):
        """测试IPv6地址"""
        request = ToolRequest(parameters={
            "host": "2001:4860:4860::8888",  # Google DNS IPv6
            "port": 53
        })
        
        with patch('asyncio.open_connection') as mock_open_connection:
            mock_reader = MagicMock()
            mock_writer = MagicMock()
            mock_open_connection.return_value = (mock_reader, mock_writer)
            
            with patch('time.perf_counter') as mock_time:
                mock_time.side_effect = [0.0, 0.08]  # 80ms延迟
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert response.data["port_open"] is True
                assert response.data["host"] == "2001:4860:4860::8888"
    
    @pytest.mark.asyncio
    async def test_tcping_ssl_port(self):
        """测试SSL端口(443)"""
        request = ToolRequest(parameters={
            "host": "github.com",
            "port": 443
        })
        
        with patch('asyncio.open_connection') as mock_open_connection:
            mock_reader = MagicMock()
            mock_writer = MagicMock()
            mock_open_connection.return_value = (mock_reader, mock_writer)
            
            with patch('time.perf_counter') as mock_time:
                mock_time.side_effect = [0.0, 0.25]  # 250ms延迟
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert response.data["port_open"] is True
                assert response.data["port"] == 443
    
    @pytest.mark.asyncio
    async def test_tcping_invalid_port(self):
        """测试无效端口号"""
        request = ToolRequest(parameters={
            "host": "example.com",
            "port": 99999  # 无效端口
        })
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
        assert "port" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_tcping_very_fast_response(self):
        """测试极快响应（本地连接）"""
        request = ToolRequest(parameters={
            "host": "127.0.0.1",
            "port": 8080
        })
        
        with patch('asyncio.open_connection') as mock_open_connection:
            mock_reader = MagicMock()
            mock_writer = MagicMock()
            mock_open_connection.return_value = (mock_reader, mock_writer)
            
            with patch('time.perf_counter') as mock_time:
                mock_time.side_effect = [0.0, 0.001]  # 1ms延迟
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert response.data["port_open"] is True
                assert response.data["response_time_ms"] == 1.0