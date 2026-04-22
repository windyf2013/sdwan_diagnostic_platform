"""TraceRouteTool单元测试"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.implementations.network.traceroute import TraceRouteTool


class TestTraceRouteTool:
    """TraceRouteTool测试类"""
    
    def setup_method(self):
        """测试初始化"""
        self.tool = TraceRouteTool()
        self.ctx = FlowContext(
            flow_id="test-flow",
            flow_name="test",
            trace_id="test-trace-123"
        )
    
    def _create_mock_process(self, stdout: str, returncode: int = 0):
        """创建mock进程对象"""
        mock_process = AsyncMock()
        mock_process.returncode = returncode
        mock_process.communicate = AsyncMock(
            return_value=(stdout.encode('utf-8'), b"")
        )
        return mock_process
    
    def _create_linux_mock_process(self, stdout: str, returncode: int = 0):
        """创建Linux traceroute格式的mock进程对象"""
        mock_process = AsyncMock()
        mock_process.returncode = returncode
        mock_process.communicate = AsyncMock(
            return_value=(stdout.encode('utf-8'), b"")
        )
        return mock_process
    
    @pytest.mark.asyncio
    async def test_traceroute_success(self):
        """测试Traceroute成功场景 - Linux格式"""
        request = ToolRequest(
            tool_name="traceroute",
            parameters={"host": "8.8.8.8", "max_hops": 5}
        )
        
        # Linux traceroute输出格式
        mock_stdout = """traceroute to 8.8.8.8 (8.8.8.8), 5 hops max, 60 byte packets
 1  192.168.1.1 (192.168.1.1)  1.234 ms  1.345 ms  1.456 ms
 2  10.0.0.1 (10.0.0.1)  5.123 ms  4.567 ms  5.890 ms
 3  203.0.113.1 (203.0.113.1)  10.123 ms  11.456 ms  10.789 ms
 4  8.8.8.8 (8.8.8.8)  15.123 ms  16.456 ms  15.789 ms
"""
        mock_process = self._create_linux_mock_process(mock_stdout)
        
        with patch.object(self.tool, '_is_windows', False):
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_process
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert len(response.data["hops"]) == 4
                assert response.data["hops"][0]["hop"] == 1
                assert response.data["hops"][0]["ip"] == "192.168.1.1"
                assert response.data["hops"][3]["ip"] == "8.8.8.8"
                assert response.data["hops"][0]["hostname"] is None  # hostname == ip 时返回None
                assert response.data["hops"][0]["rtts"] == [1.234, 1.345, 1.456]

    
    @pytest.mark.asyncio
    async def test_traceroute_missing_host(self):
        """测试缺少host参数"""
        request = ToolRequest(
            tool_name="traceroute",
            parameters={}
        )
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
    
    @pytest.mark.asyncio
    async def test_traceroute_timeout(self):
        """测试Traceroute超时"""
        request = ToolRequest(
            tool_name="traceroute",
            parameters={"host": "192.0.2.1"}
        )
        
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError("Command timed out"))
        
        with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_process
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_TIMEOUT"
    
    @pytest.mark.asyncio
    async def test_traceroute_with_asterisks(self):
        """测试包含星号的路由跳 - Linux格式"""
        request = ToolRequest(
            tool_name="traceroute",
            parameters={"host": "example.com"}
        )
        
        # Linux格式：星号表示超时
        mock_stdout = """traceroute to example.com (93.184.216.34), 30 hops max, 60 byte packets
 1  192.168.1.1 (192.168.1.1)  1.234 ms  1.345 ms  1.456 ms
 2  10.0.0.1 (10.0.0.1)  5.123 ms  4.567 ms  5.890 ms
 3  * * *
 4  93.184.216.34 (93.184.216.34)  15.123 ms  16.456 ms  15.789 ms
"""
        mock_process = self._create_linux_mock_process(mock_stdout)
        
        with patch.object(self.tool, '_is_windows', False):
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_process
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                hops = response.data["hops"]
                assert len(hops) == 3  # 第3行* * * 不匹配Linux正则，所以只有3跳
                assert hops[0]["ip"] == "192.168.1.1"
                assert hops[1]["ip"] == "10.0.0.1"
                assert hops[2]["ip"] == "93.184.216.34"

    
    @pytest.mark.asyncio
    async def test_traceroute_windows_format(self):
        """测试Windows格式输出解析"""
        request = ToolRequest(
            tool_name="traceroute",
            parameters={"host": "baidu.com"}
        )
        
        # Windows tracert格式
        mock_stdout = """
Tracing route to baidu.com [39.156.66.10] over a maximum of 30 hops:

  1     1 ms     1 ms     1 ms  192.168.1.1
  2     5 ms     4 ms     5 ms  10.0.0.1
  3    10 ms    11 ms    10 ms  39.156.66.10

Trace complete.
"""
        mock_process = self._create_mock_process(mock_stdout)
        
        with patch.object(self.tool, '_is_windows', True):
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_process
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert len(response.data["hops"]) == 3
                assert response.data["hops"][0]["ip"] == "192.168.1.1"
                assert response.data["hops"][2]["ip"] == "39.156.66.10"
    
    @pytest.mark.asyncio
    async def test_traceroute_windows_with_asterisks(self):
        """测试Windows格式包含星号的路由跳"""
        request = ToolRequest(
            tool_name="traceroute",
            parameters={"host": "example.com"}
        )
        
        mock_stdout = """
Tracing route to example.com [93.184.216.34] over a maximum of 30 hops:

  1     1 ms     1 ms     1 ms  192.168.1.1
  2     5 ms     4 ms     5 ms  10.0.0.1
  3     *        *        *     Request timed out.
  4    15 ms    16 ms    15 ms  93.184.216.34

Trace complete.
"""
        mock_process = self._create_mock_process(mock_stdout)
        
        with patch.object(self.tool, '_is_windows', True):
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_process
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                hops = response.data["hops"]
                assert len(hops) == 4
                assert hops[2]["ip"] == "*"
                assert hops[2]["rtts"] == []
    
    @pytest.mark.asyncio
    async def test_traceroute_windows_chinese_output(self):
        """测试Windows中文输出解析"""
        request = ToolRequest(
            tool_name="traceroute",
            parameters={"host": "baidu.com"}
        )
        
        mock_stdout = """
通过最多 30 个跃点跟踪到 baidu.com [39.156.66.10] 的路由:

  1     1 ms     1 ms     1 ms  192.168.1.1
  2     5 ms     4 ms     5 ms  10.0.0.1
  3    10 ms    11 ms    10 ms  39.156.66.10

跟踪完成。
"""
        mock_process = self._create_mock_process(mock_stdout)
        
        with patch.object(self.tool, '_is_windows', True):
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_process
                
                response = await self.tool.execute(request, self.ctx)
                
                assert response.success is True
                assert len(response.data["hops"]) == 3
    
    @pytest.mark.asyncio
    async def test_traceroute_unreachable(self):
        """测试目标不可达"""
        request = ToolRequest(
            tool_name="traceroute",
            parameters={"host": "unreachable-host"}
        )
        
        mock_process = self._create_mock_process(
            "Unable to resolve target system name unreachable-host.",
            returncode=1
        )
        
        with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_process
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True  # traceroute可能部分成功
            assert len(response.data["hops"]) == 0
    
    @pytest.mark.asyncio
    async def test_traceroute_invalid_max_hops(self):
        """测试无效max_hops参数"""
        request = ToolRequest(
            tool_name="traceroute",
            parameters={
                "host": "example.com",
                "max_hops": 100  # 超过最大值64
            }
        )
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_001"
        assert "max_hops" in response.error_message
    
    @pytest.mark.asyncio
    async def test_traceroute_general_exception(self):
        """测试通用异常"""
        request = ToolRequest(
            tool_name="traceroute",
            parameters={"host": "example.com"}
        )
        
        with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Exception("系统错误")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_002"
    
    def test_parse_rtt_normal(self):
        """测试RTT解析-正常值"""
        rtt = self.tool._parse_rtt("1.234")
        assert rtt == 1.234
    
    def test_parse_rtt_asterisk(self):
        """测试RTT解析-星号"""
        rtt = self.tool._parse_rtt("*")
        assert rtt is None
    
    def test_parse_rtt_empty(self):
        """测试RTT解析-空值"""
        rtt = self.tool._parse_rtt("")
        assert rtt is None
    
    def test_parse_rtt_invalid(self):
        """测试RTT解析-无效值"""
        rtt = self.tool._parse_rtt("abc")
        assert rtt is None
    
    def test_parse_target_ip_only(self):
        """测试目标解析-纯IP"""
        ip, hostname = self.tool._parse_target("192.168.1.1")
        assert ip == "192.168.1.1"
        assert hostname is None
    
    def test_parse_target_hostname_with_ip(self):
        """测试目标解析-主机名+IP"""
        ip, hostname = self.tool._parse_target("router.local [192.168.1.1]")
        assert ip == "192.168.1.1"
        assert hostname == "router.local"
    
    def test_parse_target_unknown(self):
        """测试目标解析-未知格式"""
        ip, hostname = self.tool._parse_target("some-unknown-format")
        assert ip is None
        assert hostname == "some-unknown-format"
    
    def test_calculate_hop_stats_empty(self):
        """测试跳统计-空RTT列表"""
        stats = self.tool._calculate_hop_stats([])
        assert stats["rtt_min"] is None
        assert stats["rtt_avg"] is None
        assert stats["rtt_max"] is None
        assert stats["loss_rate"] == 1.0
    
    def test_calculate_hop_stats_normal(self):
        """测试跳统计-正常值"""
        stats = self.tool._calculate_hop_stats([10.0, 20.0, 30.0])
        assert stats["rtt_min"] == 10.0
        assert stats["rtt_avg"] == 20.0
        assert stats["rtt_max"] == 30.0
        assert stats["loss_rate"] == 0.0
    
    def test_calculate_hop_stats_partial(self):
        """测试跳统计-部分丢包"""
        stats = self.tool._calculate_hop_stats([10.0, 20.0])
        assert stats["rtt_min"] == 10.0
        assert stats["rtt_avg"] == 15.0
        assert stats["rtt_max"] == 20.0
        assert stats["loss_rate"] == 1/3
    
    def test_resolve_hostname_success(self):
        """测试主机名解析成功"""
        with patch('socket.gethostbyname') as mock_gethost:
            mock_gethost.return_value = "93.184.216.34"
            ip = self.tool._resolve_hostname("example.com")
            assert ip == "93.184.216.34"
    
    def test_resolve_hostname_failed(self):
        """测试主机名解析失败"""
        with patch('socket.gethostbyname') as mock_gethost:
            mock_gethost.side_effect = Exception("解析失败")
            ip = self.tool._resolve_hostname("nonexistent.local")
            assert ip is None
    
    def test_detect_os(self):
        """测试操作系统检测"""
        with patch('platform.system') as mock_system:
            mock_system.return_value = "Windows"
            tool = TraceRouteTool()
            assert tool._is_windows is True
        
        with patch('platform.system') as mock_system:
            mock_system.return_value = "Linux"
            tool = TraceRouteTool()
            assert tool._is_windows is False
