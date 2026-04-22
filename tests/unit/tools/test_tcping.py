"""TcpPortTool单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import asyncio
import socket


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
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "example.com",
                "port": 80,
                "timeout": 5,
                "count": 1
            }
        )
        
        with patch.object(self.tool, '_resolve_hostname', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "93.184.216.34"
            
            with patch.object(self.tool, '_probe_port', new_callable=AsyncMock) as mock_probe:
                mock_probe.return_value = [{
                    "success": True,
                    "response_time": 150.0,
                    "error": None,
                    "banner": None
                }]
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert response.data["port_open"] is True
                assert response.data["host"] == "example.com"
                assert response.data["port"] == 80
                assert response.data["resolved_ip"] == "93.184.216.34"
                assert response.data["response_times"] == [150.0]
                assert response.data["response_time_avg"] == 150.0
                assert response.data["response_time_min"] == 150.0
                assert response.data["response_time_max"] == 150.0
                assert response.data["loss_rate"] == 0.0
                assert response.data["total_probes"] == 1
                assert response.data["successful_probes"] == 1
    
    @pytest.mark.asyncio
    async def test_tcping_multiple_probes(self):
        """测试多次探测"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "example.com",
                "port": 80,
                "timeout": 5,
                "count": 3
            }
        )
        
        with patch.object(self.tool, '_resolve_hostname', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "93.184.216.34"
            
            with patch.object(self.tool, '_probe_port', new_callable=AsyncMock) as mock_probe:
                mock_probe.return_value = [
                    {"success": True, "response_time": 100.0, "error": None, "banner": None},
                    {"success": True, "response_time": 150.0, "error": None, "banner": None},
                    {"success": False, "response_time": None, "error": "timeout", "banner": None}
                ]
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert response.data["port_open"] is True
                assert response.data["response_times"] == [100.0, 150.0]
                assert response.data["response_time_avg"] == 125.0
                assert response.data["response_time_min"] == 100.0
                assert response.data["response_time_max"] == 150.0
                assert response.data["loss_rate"] == 1/3
                assert response.data["total_probes"] == 3
                assert response.data["successful_probes"] == 2
    
    @pytest.mark.asyncio
    async def test_tcping_missing_host(self):
        """测试缺少host参数"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={"port": 80}
        )
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
        assert "host" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_tcping_missing_port(self):
        """测试缺少port参数"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={"host": "example.com"}
        )
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_001"
        assert "port" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_tcping_invalid_port(self):
        """测试无效端口号"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "example.com",
                "port": 99999  # 无效端口
            }
        )
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_001"
        assert "port" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_tcping_invalid_count(self):
        """测试无效count参数"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "example.com",
                "port": 80,
                "count": 0  # 无效count
            }
        )
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_001"
        assert "count" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_tcping_connection_refused(self):
        """测试连接被拒绝"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "localhost",
                "port": 9999,
                "count": 1
            }
        )
        
        with patch.object(self.tool, '_resolve_hostname', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "127.0.0.1"
            
            with patch.object(self.tool, '_probe_port', new_callable=AsyncMock) as mock_probe:
                mock_probe.return_value = [{
                    "success": False,
                    "response_time": None,
                    "error": "连接被拒绝",
                    "banner": None
                }]
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True  # 连接被拒绝也是一种有效结果
                assert response.data["port_open"] is False
                assert response.data["response_times"] == []
                assert response.data["loss_rate"] == 1.0
    
    @pytest.mark.asyncio
    async def test_tcping_all_failed(self):
        """测试所有探测都失败"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "unreachable-host.local",
                "port": 443,
                "count": 2
            }
        )
        
        with patch.object(self.tool, '_resolve_hostname', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "192.168.1.99"
            
            with patch.object(self.tool, '_probe_port', new_callable=AsyncMock) as mock_probe:
                mock_probe.return_value = [
                    {"success": False, "response_time": None, "error": "timeout", "banner": None},
                    {"success": False, "response_time": None, "error": "timeout", "banner": None}
                ]
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert response.data["port_open"] is False
                assert response.data["response_times"] == []
                assert response.data["loss_rate"] == 1.0
                assert response.data["response_time_avg"] is None
                assert response.data["response_time_min"] is None
                assert response.data["response_time_max"] is None
    
    @pytest.mark.asyncio
    async def test_tcping_with_banner(self):
        """测试获取banner"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "example.com",
                "port": 22,
                "count": 1
            }
        )
        
        with patch.object(self.tool, '_resolve_hostname', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "93.184.216.34"
            
            with patch.object(self.tool, '_probe_port', new_callable=AsyncMock) as mock_probe:
                mock_probe.return_value = [{
                    "success": True,
                    "response_time": 50.0,
                    "error": None,
                    "banner": "SSH-2.0-OpenSSH_8.9"
                }]
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert response.data["port_open"] is True
                assert response.data["banner"] == "SSH-2.0-OpenSSH_8.9"
    
    @pytest.mark.asyncio
    async def test_tcping_hostname_resolution_failed(self):
        """测试主机名解析失败"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "nonexistent-domain.local",
                "port": 80
            }
        )
        
        with patch.object(self.tool, '_resolve_hostname', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = None
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_002"
            assert "无法解析主机名" in response.error_message
    
    @pytest.mark.asyncio
    async def test_tcping_default_parameters(self):
        """测试默认参数"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "example.com",
                "port": 80
            }
        )
        
        with patch.object(self.tool, '_resolve_hostname', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "93.184.216.34"
            
            with patch.object(self.tool, '_probe_port', new_callable=AsyncMock) as mock_probe:
                mock_probe.return_value = [{
                    "success": True,
                    "response_time": 100.0,
                    "error": None,
                    "banner": None
                }]
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert response.data["total_probes"] == 3  # 默认count=3
                assert response.data["response_time_avg"] == 100.0
    
    @pytest.mark.asyncio
    async def test_tcping_with_source_ip(self):
        """测试指定源IP"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "example.com",
                "port": 80,
                "source_ip": "192.168.1.100",
                "count": 1
            }
        )
        
        with patch.object(self.tool, '_resolve_hostname', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "93.184.216.34"
            
            with patch.object(self.tool, '_probe_port', new_callable=AsyncMock) as mock_probe:
                mock_probe.return_value = [{
                    "success": True,
                    "response_time": 120.0,
                    "error": None,
                    "banner": None
                }]
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert response.data["port_open"] is True

    @pytest.mark.asyncio
    async def test_tcping_timeout_error(self):
        """测试超时异常"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "example.com",
                "port": 80,
                "count": 1
            }
        )
        
        with patch.object(self.tool, '_resolve_hostname', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = asyncio.TimeoutError("连接超时")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_TIMEOUT"

    @pytest.mark.asyncio
    async def test_tcping_general_exception(self):
        """测试通用异常"""
        request = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": "example.com",
                "port": 80,
                "count": 1
            }
        )
        
        with patch.object(self.tool, '_resolve_hostname', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = Exception("未知错误")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_002"

    @pytest.mark.asyncio
    async def test_tcping_resolve_hostname_ipv4(self):
        """测试主机名解析IPv4成功"""
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop_instance = AsyncMock()
            mock_loop.return_value = mock_loop_instance
            mock_loop_instance.getaddrinfo = AsyncMock(return_value=[(socket.AF_INET, 1, 6, '', ('93.184.216.34', 0))])
            
            result = await self.tool._resolve_hostname("example.com")
            assert result == "93.184.216.34"

    @pytest.mark.asyncio
    async def test_tcping_resolve_hostname_ipv6_fallback(self):
        """测试主机名解析IPv4失败后回退到IPv6"""
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop_instance = AsyncMock()
            mock_loop.return_value = mock_loop_instance
            # IPv4失败
            mock_loop_instance.getaddrinfo = AsyncMock()
            mock_loop_instance.getaddrinfo.side_effect = [
                OSError("IPv4不可用"),  # 第一次调用IPv4失败
                [(socket.AF_INET6, 1, 6, '', ('::1', 0, 0, 0))]  # 第二次调用IPv6成功
            ]
            
            result = await self.tool._resolve_hostname("localhost")
            assert result == "::1"

    @pytest.mark.asyncio
    async def test_tcping_resolve_hostname_failed(self):
        """测试主机名解析完全失败"""
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop_instance = AsyncMock()
            mock_loop.return_value = mock_loop_instance
            mock_loop_instance.getaddrinfo = AsyncMock(side_effect=OSError("解析失败"))
            
            result = await self.tool._resolve_hostname("nonexistent.example.com")
            assert result is None

    @pytest.mark.asyncio
    async def test_tcping_probe_port_connection_refused(self):
        """测试探测端口连接被拒绝"""
        with patch.object(self.tool, '_create_connection', new_callable=AsyncMock) as mock_conn:
            mock_conn.side_effect = ConnectionRefusedError("连接被拒绝")
            
            results = await self.tool._probe_port("127.0.0.1", 9999, 1, 5)
            
            assert len(results) == 1
            assert results[0]["success"] is False
            assert results[0]["error"] == "连接被拒绝"

    @pytest.mark.asyncio
    async def test_tcping_probe_port_os_error(self):
        """测试探测端口OS错误"""
        with patch.object(self.tool, '_create_connection', new_callable=AsyncMock) as mock_conn:
            mock_conn.side_effect = OSError("网络不可达")
            
            results = await self.tool._probe_port("10.0.0.1", 80, 1, 5)
            
            assert len(results) == 1
            assert results[0]["success"] is False
            assert "网络错误" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_tcping_probe_port_general_exception(self):
        """测试探测端口通用异常"""
        with patch.object(self.tool, '_create_connection', new_callable=AsyncMock) as mock_conn:
            mock_conn.side_effect = Exception("未知错误")
            
            results = await self.tool._probe_port("10.0.0.1", 80, 1, 5)
            
            assert len(results) == 1
            assert results[0]["success"] is False
            assert results[0]["error"] == "未知错误"

    @pytest.mark.asyncio
    async def test_tcping_probe_port_timeout(self):
        """测试探测端口超时"""
        with patch.object(self.tool, '_create_connection', new_callable=AsyncMock) as mock_conn:
            mock_conn.side_effect = asyncio.TimeoutError("超时")
            
            results = await self.tool._probe_port("10.0.0.1", 80, 1, 5)
            
            assert len(results) == 1
            assert results[0]["success"] is False
            assert results[0]["error"] == "连接超时"

    @pytest.mark.asyncio
    async def test_tcping_read_banner_success(self):
        """测试读取banner成功"""
        reader = AsyncMock()
        reader.read = AsyncMock(return_value=b"SSH-2.0-OpenSSH_8.9\r\n")
        
        banner = await self.tool._read_banner(reader, 5)
        assert banner == "SSH-2.0-OpenSSH_8.9"

    @pytest.mark.asyncio
    async def test_tcping_read_banner_timeout(self):
        """测试读取banner超时"""
        reader = AsyncMock()
        reader.read = AsyncMock(side_effect=asyncio.TimeoutError())
        
        banner = await self.tool._read_banner(reader, 5)
        assert banner is None

    @pytest.mark.asyncio
    async def test_tcping_read_banner_empty(self):
        """测试读取banner为空"""
        reader = AsyncMock()
        reader.read = AsyncMock(return_value=b"")
        
        banner = await self.tool._read_banner(reader, 5)
        assert banner is None

    def test_tcping_calculate_statistics_empty(self):
        """测试统计信息计算-空结果"""
        stats = self.tool._calculate_statistics([])
        assert stats["port_open"] is False
        assert stats["response_times"] == []
        assert stats["response_time_avg"] is None
        assert stats["response_time_min"] is None
        assert stats["response_time_max"] is None
        assert stats["loss_rate"] == 1.0
        assert stats["successful_probes"] == 0

    def test_tcping_calculate_statistics_single(self):
        """测试统计信息计算-单次结果"""
        results = [{"success": True, "response_time": 100.0, "banner": "test"}]
        stats = self.tool._calculate_statistics(results)
        assert stats["port_open"] is True
        assert stats["response_times"] == [100.0]
        assert stats["response_time_avg"] == 100.0
        assert stats["response_time_min"] == 100.0
        assert stats["response_time_max"] == 100.0
        assert stats["response_time_stddev"] == 0.0
        assert stats["loss_rate"] == 0.0
        assert stats["successful_probes"] == 1
        assert stats["banner"] == "test"

    def test_tcping_calculate_statistics_multiple(self):
        """测试统计信息计算-多次结果"""
        results = [
            {"success": True, "response_time": 100.0, "banner": None},
            {"success": True, "response_time": 200.0, "banner": None},
            {"success": False, "response_time": None, "banner": None},
        ]
        stats = self.tool._calculate_statistics(results)
        assert stats["port_open"] is True
        assert stats["response_times"] == [100.0, 200.0]
        assert stats["response_time_avg"] == 150.0
        assert stats["response_time_min"] == 100.0
        assert stats["response_time_max"] == 200.0
        assert stats["loss_rate"] == 1/3
        assert stats["successful_probes"] == 2
