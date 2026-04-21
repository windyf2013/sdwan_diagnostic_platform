"""MtrTool单元测试"""

from unittest.mock import MagicMock, patch
import pytest
import asyncio

from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.implementations.network.mtr import MtrTool


class TestMtrTool:
    """MtrTool测试类"""
    
    def setup_method(self):
        """测试初始化"""
        self.tool = MtrTool()
        self.ctx = FlowContext(
            flow_id="test-flow",
            flow_name="test",
            trace_id="test-trace-123"
        )
    
    @pytest.mark.asyncio
    async def test_mtr_success(self):
        """测试MTR成功执行"""
        request = ToolRequest(parameters={
            "host": "example.com",
            "count": 3,
            "interval": 1
        })
        
        # Mock ToolDispatcher
        with patch('sdwan_desktop.tools.implementations.network.mtr.ToolDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher
            
            # Mock traceroute结果
            mock_trace_response = ToolResponse(
                success=True,
                data={
                    "hops": [
                        {"hop": 1, "ip": "192.168.1.1", "hostname": "gateway.local", "rtts": [5.2, 5.5, 5.3]},
                        {"hop": 2, "ip": "10.0.0.1", "hostname": "isp-gw", "rtts": [15.8, 16.2, 15.9]},
                        {"hop": 3, "ip": "203.0.113.1", "hostname": "core-router", "rtts": [25.1, 25.3, 25.0]},
                        {"hop": 4, "ip": "93.184.216.34", "hostname": "example.com", "rtts": [35.5, 35.8, 35.6]}
                    ]
                },
                trace_id=self.ctx.trace_id
            )
            
            # Mock ping结果
            mock_ping_responses = [
                ToolResponse(success=True, data={"rtt_avg": 5.3, "loss_rate": 0.0}, trace_id=self.ctx.trace_id),
                ToolResponse(success=True, data={"rtt_avg": 16.0, "loss_rate": 0.0}, trace_id=self.ctx.trace_id),
                ToolResponse(success=True, data={"rtt_avg": 25.1, "loss_rate": 0.0}, trace_id=self.ctx.trace_id),
                ToolResponse(success=True, data={"rtt_avg": 35.6, "loss_rate": 0.0}, trace_id=self.ctx.trace_id)
            ]
            
            # 设置dispatcher.dispatch的返回值
            mock_dispatcher.dispatch.side_effect = [mock_trace_response] + mock_ping_responses
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            # 验证返回结构
            assert "target" in data
            assert data["target"] == "example.com"
            assert "hops" in data
            assert len(data["hops"]) == 4
            
            # 验证每跳统计信息
            hop1 = data["hops"][0]
            assert hop1["hop"] == 1
            assert hop1["ip"] == "192.168.1.1"
            assert hop1["rtt_avg"] == 5.3
            assert hop1["loss_rate"] == 0.0
            
            # 验证整体统计
            assert "summary" in data
            assert data["summary"]["total_hops"] == 4
            assert data["summary"]["max_rtt"] == 35.6
    
    @pytest.mark.asyncio
    async def test_mtr_missing_host(self):
        """测试缺少host参数"""
        request = ToolRequest(parameters={"count": 3})
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
        assert "host" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_mtr_traceroute_failed(self):
        """测试traceroute失败"""
        request = ToolRequest(parameters={
            "host": "unreachable.com",
            "count": 2
        })
        
        with patch('sdwan_desktop.tools.implementations.network.mtr.ToolDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher
            
            # Mock traceroute失败
            mock_trace_response = ToolResponse(
                success=False,
                error_code="TOOL_002",
                error_message="traceroute failed",
                trace_id=self.ctx.trace_id
            )
            
            mock_dispatcher.dispatch.return_value = mock_trace_response
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_002"
            assert "traceroute" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_mtr_partial_ping_failure(self):
        """测试部分ping失败"""
        request = ToolRequest(parameters={
            "host": "example.com",
            "count": 2
        })
        
        with patch('sdwan_desktop.tools.implementations.network.mtr.ToolDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher
            
            # Mock traceroute成功
            mock_trace_response = ToolResponse(
                success=True,
                data={
                    "hops": [
                        {"hop": 1, "ip": "192.168.1.1", "hostname": "gateway.local", "rtts": [5.2, 5.5]},
                        {"hop": 2, "ip": "10.0.0.1", "hostname": "isp-gw", "rtts": [15.8, 16.2]},
                        {"hop": 3, "ip": "203.0.113.1", "hostname": "core-router", "rtts": [25.1, 25.3]}
                    ]
                },
                trace_id=self.ctx.trace_id
            )
            
            # Mock部分ping失败
            mock_ping_responses = [
                ToolResponse(success=True, data={"rtt_avg": 5.3, "loss_rate": 0.0}, trace_id=self.ctx.trace_id),
                ToolResponse(success=False, error_code="TOOL_TIMEOUT", error_message="ping timeout", trace_id=self.ctx.trace_id),
                ToolResponse(success=True, data={"rtt_avg": 25.2, "loss_rate": 0.0}, trace_id=self.ctx.trace_id)
            ]
            
            mock_dispatcher.dispatch.side_effect = [mock_trace_response] + mock_ping_responses
            
            response = await self.tool.execute(request, self.ctx)
            
            # 即使部分ping失败，MTR也应该成功返回
            assert response.success is True
            data = response.data
            
            # 验证失败的跳有特殊标记
            assert len(data["hops"]) == 3
            hop2 = data["hops"][1]
            assert hop2["hop"] == 2
            assert hop2["ping_success"] is False
            assert "timeout" in hop2.get("error_message", "").lower()
    
    @pytest.mark.asyncio
    async def test_mtr_with_loss(self):
        """测试有丢包的情况"""
        request = ToolRequest(parameters={
            "host": "lossy-host.com",
            "count": 4
        })
        
        with patch('sdwan_desktop.tools.implementations.network.mtr.ToolDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher
            
            # Mock traceroute结果
            mock_trace_response = ToolResponse(
                success=True,
                data={
                    "hops": [
                        {"hop": 1, "ip": "192.168.1.1", "hostname": "gateway.local", "rtts": [5.2, 5.5, 5.3, 5.4]},
                        {"hop": 2, "ip": "10.0.0.1", "hostname": "isp-gw", "rtts": [15.8, 16.2, 15.9, 16.1]}
                    ]
                },
                trace_id=self.ctx.trace_id
            )
            
            # Mock有丢包的ping结果
            mock_ping_responses = [
                ToolResponse(success=True, data={"rtt_avg": 5.35, "loss_rate": 0.0}, trace_id=self.ctx.trace_id),
                ToolResponse(success=True, data={"rtt_avg": 16.0, "loss_rate": 0.25}, trace_id=self.ctx.trace_id)  # 25%丢包
            ]
            
            mock_dispatcher.dispatch.side_effect = [mock_trace_response] + mock_ping_responses
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            # 验证丢包率
            hop2 = data["hops"][1]
            assert hop2["loss_rate"] == 0.25
            assert hop2["rtt_avg"] == 16.0
    
    @pytest.mark.asyncio
    async def test_mtr_single_hop(self):
        """测试单跳路由"""
        request = ToolRequest(parameters={
            "host": "localhost",
            "count": 2
        })
        
        with patch('sdwan_desktop.tools.implementations.network.mtr.ToolDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher
            
            # Mock traceroute结果（只有一跳）
            mock_trace_response = ToolResponse(
                success=True,
                data={
                    "hops": [
                        {"hop": 1, "ip": "127.0.0.1", "hostname": "localhost", "rtts": [0.5, 0.6]}
                    ]
                },
                trace_id=self.ctx.trace_id
            )
            
            # Mock ping结果
            mock_ping_response = ToolResponse(
                success=True,
                data={"rtt_avg": 0.55, "loss_rate": 0.0},
                trace_id=self.ctx.trace_id
            )
            
            mock_dispatcher.dispatch.side_effect = [mock_trace_response, mock_ping_response]
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            assert len(data["hops"]) == 1
            assert data["summary"]["total_hops"] == 1
            assert data["hops"][0]["rtt_avg"] == 0.55
    
    @pytest.mark.asyncio
    async def test_mtr_timeout(self):
        """测试MTR超时"""
        request = ToolRequest(parameters={
            "host": "slow-host.com",
            "count": 5,
            "timeout": 1  # 短超时
        })
        
        with patch('sdwan_desktop.tools.implementations.network.mtr.ToolDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher
            
            # Mock traceroute成功
            mock_trace_response = ToolResponse(
                success=True,
                data={
                    "hops": [
                        {"hop": 1, "ip": "192.168.1.1", "hostname": "gateway.local", "rtts": [5.2, 5.5, 5.3, 5.4, 5.3]},
                        {"hop": 2, "ip": "10.0.0.1", "hostname": "isp-gw", "rtts": [15.8, 16.2, 15.9, 16.1, 16.0]}
                    ]
                },
                trace_id=self.ctx.trace_id
            )
            
            # Mock第一个ping成功，第二个ping超时
            mock_ping_responses = [
                ToolResponse(success=True, data={"rtt_avg": 5.34, "loss_rate": 0.0}, trace_id=self.ctx.trace_id),
                ToolResponse(success=False, error_code="TOOL_TIMEOUT", error_message="ping timeout", trace_id=self.ctx.trace_id)
            ]
            
            mock_dispatcher.dispatch.side_effect = [mock_trace_response] + mock_ping_responses
            
            response = await self.tool.execute(request, self.ctx)
            
            # 即使有超时，MTR也应该成功返回
            assert response.success is True
            data = response.data
            
            # 验证超时的跳有标记
            hop2 = data["hops"][1]
            assert hop2["ping_success"] is False
            assert "timeout" in hop2.get("error_message", "").lower()
    
    @pytest.mark.asyncio
    async def test_mtr_concurrent_ping(self):
        """测试并发ping执行"""
        request = ToolRequest(parameters={
            "host": "example.com",
            "count": 3,
            "concurrent": True  # 启用并发
        })
        
        with patch('sdwan_desktop.tools.implementations.network.mtr.ToolDispatcher') as mock_dispatcher_class, \
             patch('asyncio.gather') as mock_gather:
            
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher
            
            # Mock traceroute结果
            mock_trace_response = ToolResponse(
                success=True,
                data={
                    "hops": [
                        {"hop": 1, "ip": "192.168.1.1", "hostname": "gateway.local", "rtts": [5.2, 5.5, 5.3]},
                        {"hop": 2, "ip": "10.0.0.1", "hostname": "isp-gw", "rtts": [15.8, 16.2, 15.9]}
                    ]
                },
                trace_id=self.ctx.trace_id
            )
            
            # Mock并发ping结果
            mock_ping_responses = [
                ToolResponse(success=True, data={"rtt_avg": 5.33, "loss_rate": 0.0}, trace_id=self.ctx.trace_id),
                ToolResponse(success=True, data={"rtt_avg": 15.97, "loss_rate": 0.0}, trace_id=self.ctx.trace_id)
            ]
            
            mock_gather.return_value = mock_ping_responses
            mock_dispatcher.dispatch.return_value = mock_trace_response
            
            response = await self.tool.execute(request, self.ctx)
            
            # 验证并发执行被调用
            mock_gather.assert_called_once()
            assert response.success is True
    
    @pytest.mark.asyncio
    async def test_mtr_invalid_count(self):
        """测试无效的count参数"""
        request = ToolRequest(parameters={
            "host": "example.com",
            "count": 0  # 无效值
        })
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
        assert "count" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_mtr_ipv6_target(self):
        """测试IPv6目标"""
        request = ToolRequest(parameters={
            "host": "2001:4860:4860::8888",  # Google DNS IPv6
            "count": 2
        })
        
        with patch('sdwan_desktop.tools.implementations.network.mtr.ToolDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher
            
            # Mock traceroute结果
            mock_trace_response = ToolResponse(
                success=True,
                data={
                    "hops": [
                        {"hop": 1, "ip": "fe80::1", "hostname": "ipv6-gateway", "rtts": [2.1, 2.3]},
                        {"hop": 2, "ip": "2001:4860:4860::8888", "hostname": "dns.google", "rtts": [15.2, 15.5]}
                    ]
                },
                trace_id=self.ctx.trace_id
            )
            
            # Mock ping结果
            mock_ping_responses = [
                ToolResponse(success=True, data={"rtt_avg": 2.2, "loss_rate": 0.0}, trace_id=self.ctx.trace_id),
                ToolResponse(success=True, data={"rtt_avg": 15.35, "loss_rate": 0.0}, trace_id=self.ctx.trace_id)
            ]
            
            mock_dispatcher.dispatch.side_effect = [mock_trace_response] + mock_ping_responses
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            assert data["target"] == "2001:4860:4860::8888"
            assert data["hops"][0]["ip"] == "fe80::1"