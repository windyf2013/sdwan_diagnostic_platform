"""TraceRouteTool单元测试"""

from unittest.mock import MagicMock, patch
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
    
    @pytest.mark.asyncio
    async def test_traceroute_success(self):
        """测试Traceroute成功场景"""
        request = ToolRequest(parameters={"host": "8.8.8.8", "max_hops": 5})
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = """
Tracing route to 8.8.8.8 over a maximum of 5 hops

  1    <1 ms    <1 ms    <1 ms  192.168.1.1
  2     5 ms     4 ms     5 ms  10.0.0.1
  3    10 ms    11 ms    10 ms  203.0.113.1
  4    15 ms    16 ms    15 ms  8.8.8.8

Trace complete.
"""
            mock_run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            assert len(response.data["hops"]) == 4
            assert response.data["hops"][0]["hop"] == 1
            assert response.data["hops"][0]["ip"] == "192.168.1.1"
            assert response.data["hops"][3]["ip"] == "8.8.8.8"
    
    @pytest.mark.asyncio
    async def test_traceroute_missing_host(self):
        """测试缺少host参数"""
        request = ToolRequest(parameters={})
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
    
    @pytest.mark.asyncio
    async def test_traceroute_timeout(self):
        """测试Traceroute超时"""
        request = ToolRequest(parameters={"host": "192.0.2.1"})
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = TimeoutError("Command timed out")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_TIMEOUT"
    
    @pytest.mark.asyncio
    async def test_traceroute_with_asterisks(self):
        """测试包含星号的路由跳"""
        request = ToolRequest(parameters={"host": "example.com"})
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = """
Tracing route to example.com [93.184.216.34] over a maximum of 30 hops:

  1     1 ms     1 ms     1 ms  192.168.1.1
  2     5 ms     4 ms     5 ms  10.0.0.1
  3     *        *        *     Request timed out.
  4    15 ms    16 ms    15 ms  93.184.216.34

Trace complete.
"""
            mock_run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            hops = response.data["hops"]
            assert len(hops) == 4
            assert hops[2]["ip"] == "*"
            assert hops[2]["rtts"] == ["*", "*", "*"]
    
    @pytest.mark.asyncio
    async def test_traceroute_windows_chinese_output(self):
        """测试Windows中文输出解析"""
        request = ToolRequest(parameters={"host": "baidu.com"})
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = """
通过最多 30 个跃点跟踪到 baidu.com [39.156.66.10] 的路由:

  1    <1 ms    <1 ms    <1 ms  192.168.1.1
  2     5 ms     4 ms     5 ms  10.0.0.1
  3    10 ms    11 ms    10 ms  39.156.66.10

跟踪完成。
"""
            mock_run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            assert len(response.data["hops"]) == 3
    
    @pytest.mark.asyncio
    async def test_traceroute_unreachable(self):
        """测试目标不可达"""
        request = ToolRequest(parameters={"host": "unreachable-host"})
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = "Unable to resolve target system name unreachable-host."
            mock_run.return_value = mock_result
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_002"