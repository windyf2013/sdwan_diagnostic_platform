"""
ConnectivityTester 单元测试

测试连通性测试服务的以下功能：
1. 网关连通性测试
2. DNS服务器连通性测试
3. 国内外目标连通性测试
4. 全部测试聚合
5. 并发控制与异常处理

遵循 SDWAN_SPEC_PATCHES.md PATCH-001 覆盖率门槛
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.probe import (
    ProbeMetric,
    ProbeProtocol,
    ProbeResult,
    ProbeStatus,
    ProbeTarget,
)
from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.services.connectivity import ConnectivityTester, ConnectivityTestResult


class TestConnectivityTester:
    """ConnectivityTester 测试类"""

    def setup_method(self):
        """每个测试方法前初始化"""
        self.dispatcher = MagicMock()
        self.dispatcher.dispatch = AsyncMock()
        self.tester = ConnectivityTester(
            dispatcher=self.dispatcher,
            max_concurrent=5,
            probe_interval=0,
        )
        self.ctx = FlowContext(
            flow_id="test-flow",
            flow_name="test",
            trace_id="test-trace-123",
        )

    def _make_ping_response(
        self,
        success: bool = True,
        rtt_avg: float = 10.0,
        loss_rate: float = 0.0,
    ) -> ToolResponse:
        """创建模拟的ping工具响应"""
        return ToolResponse(
            success=success,
            data={
                "rtt_min": 8.0,
                "rtt_avg": rtt_avg,
                "rtt_max": 12.0,
                "rtt_stddev": 1.5,
                "loss_rate": loss_rate,
                "ttl": 64,
                "resolved_ips": [],
                "raw_output": "Ping statistics...",
            },
            trace_id=self.ctx.trace_id,
            duration_ms=50.0,
        )

    def _make_dns_response(
        self,
        success: bool = True,
        rtt_avg: float = 30.0,
        resolved_ips: List[str] = None,
    ) -> ToolResponse:
        """创建模拟的DNS查询工具响应"""
        return ToolResponse(
            success=success,
            data={
                "rtt_avg": rtt_avg,
                "resolved_ips": resolved_ips or ["1.2.3.4"],
                "response_code": 0,
            },
            trace_id=self.ctx.trace_id,
            duration_ms=30.0,
        )

    # ==================== 网关测试 ====================

    @pytest.mark.asyncio
    async def test_gateway_success(self):
        """测试网关连通性成功"""
        self.dispatcher.dispatch.return_value = self._make_ping_response()

        result = await self.tester.test_gateway("192.168.1.1", self.ctx)

        assert result.success is True
        assert result.target.host == "192.168.1.1"
        assert result.target.protocol == ProbeProtocol.ICMP
        assert result.target.count == 4
        assert result.metrics is not None
        assert result.metrics.rtt_avg == 10.0
        assert result.metrics.loss_rate == 0.0

        # 验证工具调用
        self.dispatcher.dispatch.assert_called_once()
        call_args = self.dispatcher.dispatch.call_args
        assert call_args[0][0] == "ping"

    @pytest.mark.asyncio
    async def test_gateway_timeout(self):
        """测试网关超时"""
        self.dispatcher.dispatch.side_effect = TimeoutError("Ping timeout")

        result = await self.tester.test_gateway("192.168.1.1", self.ctx)

        assert result.success is False
        assert result.status == ProbeStatus.TIMEOUT
        assert "超时" in result.error_message

    @pytest.mark.asyncio
    async def test_gateway_failure(self):
        """测试网关探测失败"""
        self.dispatcher.dispatch.return_value = self._make_ping_response(
            success=False
        )

        result = await self.tester.test_gateway("192.168.1.1", self.ctx)

        assert result.success is False
        assert result.status == ProbeStatus.FAILED

    # ==================== DNS测试 ====================

    @pytest.mark.asyncio
    async def test_domestic_dns_success(self):
        """测试国内DNS服务器连通性成功"""
        self.dispatcher.dispatch.return_value = self._make_dns_response()

        results = await self.tester.test_domestic_dns(
            ["114.114.114.114", "223.5.5.5"], self.ctx
        )

        assert len(results) == 2
        assert all(r.success for r in results)
        assert all(r.target.protocol == ProbeProtocol.DNS for r in results)
        assert self.dispatcher.dispatch.call_count == 2

    @pytest.mark.asyncio
    async def test_international_dns_success(self):
        """测试国际DNS服务器连通性成功"""
        self.dispatcher.dispatch.return_value = self._make_dns_response()

        results = await self.tester.test_international_dns(
            ["8.8.8.8", "1.1.1.1"], self.ctx
        )

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_dns_partial_failure(self):
        """测试DNS部分失败"""
        # 第一次成功，第二次失败
        self.dispatcher.dispatch.side_effect = [
            self._make_dns_response(),
            self._make_dns_response(success=False),
        ]

        results = await self.tester.test_domestic_dns(
            ["114.114.114.114", "223.5.5.5"], self.ctx
        )

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False

    # ==================== 目标连通性测试 ====================

    @pytest.mark.asyncio
    async def test_domestic_targets_icmp(self):
        """测试国内ICMP目标连通性"""
        self.dispatcher.dispatch.return_value = self._make_ping_response()

        targets_config = [
            {"host": "114.114.114.114", "type": "icmp"},
        ]

        results = await self.tester.test_domestic_targets(targets_config, self.ctx)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].target.protocol == ProbeProtocol.ICMP

    @pytest.mark.asyncio
    async def test_domestic_targets_http(self):
        """测试国内HTTP目标连通性"""
        self.dispatcher.dispatch.return_value = self._make_ping_response()

        targets_config = [
            {"host": "www.baidu.com", "type": "http"},
        ]

        results = await self.tester.test_domestic_targets(targets_config, self.ctx)

        assert len(results) == 1
        assert results[0].success is True
        # HTTP使用tcping工具
        self.dispatcher.dispatch.assert_called_once()
        call_args = self.dispatcher.dispatch.call_args
        assert call_args[0][0] == "tcping"

    @pytest.mark.asyncio
    async def test_international_targets_mixed(self):
        """测试国际混合类型目标连通性"""
        self.dispatcher.dispatch.return_value = self._make_ping_response()

        targets_config = [
            {"host": "www.google.com", "type": "http"},
            {"host": "8.8.8.8", "type": "icmp"},
        ]

        results = await self.tester.test_international_targets(
            targets_config, self.ctx
        )

        assert len(results) == 2
        assert self.dispatcher.dispatch.call_count == 2

    @pytest.mark.asyncio
    async def test_targets_empty_config(self):
        """测试空目标配置"""
        results = await self.tester.test_domestic_targets([], self.ctx)
        assert len(results) == 0

    # ==================== 全部测试 ====================

    @pytest.mark.asyncio
    async def test_all_success(self):
        """测试全部连通性测试成功"""
        self.dispatcher.dispatch.return_value = self._make_ping_response()

        result = await self.tester.test_all(
            gateway_ip="192.168.1.1",
            domestic_dns=["114.114.114.114", "223.5.5.5"],
            international_dns=["8.8.8.8", "1.1.1.1"],
            domestic_targets=[
                {"host": "www.baidu.com", "type": "http"},
                {"host": "114.114.114.114", "type": "icmp"},
            ],
            international_targets=[
                {"host": "www.google.com", "type": "http"},
                {"host": "8.8.8.8", "type": "icmp"},
            ],
            ctx=self.ctx,
        )

        assert isinstance(result, ConnectivityTestResult)
        assert result.gateway_ping is not None
        assert result.gateway_ping.success is True
        assert len(result.domestic_dns_results) == 2
        assert len(result.international_dns_results) == 2
        assert len(result.domestic_target_results) == 2
        assert len(result.international_target_results) == 2
        assert result.domestic_success_rate == 1.0
        assert result.international_success_rate == 1.0
        assert result.total_duration_ms > 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_all_with_partial_failures(self):
        """测试全部连通性测试部分失败"""
        # 网关成功，DNS部分失败，目标全部成功
        self.dispatcher.dispatch.side_effect = [
            self._make_ping_response(),  # 网关
            self._make_dns_response(),  # 国内DNS1
            self._make_dns_response(success=False),  # 国内DNS2
            self._make_dns_response(),  # 国际DNS1
            self._make_dns_response(),  # 国际DNS2
            self._make_ping_response(),  # 国内目标1
            self._make_ping_response(),  # 国内目标2
            self._make_ping_response(),  # 国际目标1
            self._make_ping_response(),  # 国际目标2
        ]

        result = await self.tester.test_all(
            gateway_ip="192.168.1.1",
            domestic_dns=["114.114.114.114", "223.5.5.5"],
            international_dns=["8.8.8.8", "1.1.1.1"],
            domestic_targets=[
                {"host": "www.baidu.com", "type": "http"},
                {"host": "114.114.114.114", "type": "icmp"},
            ],
            international_targets=[
                {"host": "www.google.com", "type": "http"},
                {"host": "8.8.8.8", "type": "icmp"},
            ],
            ctx=self.ctx,
        )

        assert result.gateway_ping.success is True
        assert result.domestic_dns_results[0].success is True
        assert result.domestic_dns_results[1].success is False
        assert result.domestic_success_rate == 1.0
        assert result.international_success_rate == 1.0

    @pytest.mark.asyncio
    async def test_all_with_exception(self):
        """测试全部连通性测试异常处理"""
        self.dispatcher.dispatch.side_effect = Exception("Unexpected error")

        result = await self.tester.test_all(
            gateway_ip="192.168.1.1",
            domestic_dns=["114.114.114.114"],
            international_dns=["8.8.8.8"],
            domestic_targets=[{"host": "www.baidu.com", "type": "http"}],
            international_targets=[{"host": "www.google.com", "type": "http"}],
            ctx=self.ctx,
        )

        assert result.gateway_ping is not None
        assert result.gateway_ping.success is False
        assert result.gateway_ping.error_message == "Unexpected error"
        # 异常在 _execute_probe 内部被捕获并返回 ProbeResult，
        # 因此 errors 列表为空（asyncio.gather 未收到 Exception）

    # ==================== 并发控制 ====================

    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        """测试并发限制"""
        self.dispatcher.dispatch.return_value = self._make_ping_response()

        # 创建大量目标测试并发限制
        targets_config = [
            {"host": f"target{i}.com", "type": "icmp"}
            for i in range(10)
        ]

        results = await self.tester.test_domestic_targets(targets_config, self.ctx)

        assert len(results) == 10
        assert all(r.success for r in results)
        assert self.dispatcher.dispatch.call_count == 10

    @pytest.mark.asyncio
    async def test_concurrent_exception_isolation(self):
        """测试并发异常隔离"""
        async def mock_dispatch(tool_name, request, ctx):
            if "target5" in request.parameters.get("host", ""):
                raise RuntimeError("Connection refused")
            return self._make_ping_response()

        self.dispatcher.dispatch = mock_dispatch

        targets_config = [
            {"host": f"target{i}.com", "type": "icmp"}
            for i in range(10)
        ]

        results = await self.tester.test_domestic_targets(targets_config, self.ctx)

        assert len(results) == 10
        # 只有target5失败
        assert results[5].success is False
        assert results[5].status == ProbeStatus.FAILED
        # 其他应该成功
        assert all(r.success for i, r in enumerate(results) if i != 5)

    # ==================== 边界情况 ====================

    @pytest.mark.asyncio
    async def test_unsupported_protocol(self):
        """测试不支持的协议"""
        # 模拟不支持的协议
        target = ProbeTarget(
            host="test.com",
            protocol="UNSUPPORTED",  # type: ignore
            count=1,
            timeout_seconds=5,
        )

        # 直接测试内部方法
        result = await self.tester._execute_probe(target, self.ctx)

        assert result.success is False
        assert "不支持" in result.error_message

    @pytest.mark.asyncio
    async def test_empty_dns_list(self):
        """测试空DNS列表"""
        results = await self.tester.test_domestic_dns([], self.ctx)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_success_rate_calculation(self):
        """测试成功率计算"""
        # 空列表
        assert self.tester._calculate_success_rate([]) == 0.0

        # 全部成功
        results = [
            ProbeResult(
                target=ProbeTarget(host="test.com", protocol=ProbeProtocol.ICMP),
                status=ProbeStatus.SUCCESS,
                success=True,
            )
            for _ in range(5)
        ]
        assert self.tester._calculate_success_rate(results) == 1.0

        # 部分成功
        results[0].success = False
        assert self.tester._calculate_success_rate(results) == 0.8

        # 全部失败
        for r in results:
            r.success = False
        assert self.tester._calculate_success_rate(results) == 0.0
