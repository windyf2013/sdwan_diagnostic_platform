"""
DnsSplitTester 单元测试

测试DNS分流测试服务的以下功能：
1. 单域名DNS分流测试
2. 多域名DNS分流测试
3. 分流差异检测逻辑
4. 并发控制与异常处理
5. 边界情况

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
from sdwan_desktop.services.dns_split import (
    DnsSplitTester,
    DnsSplitTestResult,
    DomainDnsResult,
)


class TestDnsSplitTester:
    """DnsSplitTester 测试类"""

    def setup_method(self):
        """每个测试方法前初始化"""
        self.dispatcher = MagicMock()
        self.dispatcher.dispatch = AsyncMock()
        self.tester = DnsSplitTester(
            dispatcher=self.dispatcher,
            max_concurrent=3,
        )
        self.ctx = FlowContext(
            flow_id="test-flow",
            flow_name="test",
            trace_id="test-trace-123",
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

    # ==================== 单域名测试 ====================

    @pytest.mark.asyncio
    async def test_domain_no_split(self):
        """测试域名无分流差异"""
        # 国内外DNS返回相同IP
        self.dispatcher.dispatch.return_value = self._make_dns_response(
            resolved_ips=["1.2.3.4"]
        )

        result = await self.tester.test_domain(
            domain="www.google.com",
            domestic_dns=["114.114.114.114", "223.5.5.5"],
            international_dns=["8.8.8.8", "1.1.1.1"],
            ctx=self.ctx,
        )

        assert isinstance(result, DomainDnsResult)
        assert result.domain == "www.google.com"
        assert result.is_split is False
        assert "一致" in result.split_description
        assert self.dispatcher.dispatch.call_count == 4

    @pytest.mark.asyncio
    async def test_domain_complete_split(self):
        """测试域名完全分流差异"""
        # 国内DNS返回国内IP，国际DNS返回国际IP
        self.dispatcher.dispatch.side_effect = [
            self._make_dns_response(resolved_ips=["1.2.3.4"]),  # 国内DNS1
            self._make_dns_response(resolved_ips=["1.2.3.4"]),  # 国内DNS2
            self._make_dns_response(resolved_ips=["5.6.7.8"]),  # 国际DNS1
            self._make_dns_response(resolved_ips=["5.6.7.8"]),  # 国际DNS2
        ]

        result = await self.tester.test_domain(
            domain="www.google.com",
            domestic_dns=["114.114.114.114", "223.5.5.5"],
            international_dns=["8.8.8.8", "1.1.1.1"],
            ctx=self.ctx,
        )

        assert result.is_split is True
        assert "完全不同" in result.split_description

    @pytest.mark.asyncio
    async def test_domain_partial_split(self):
        """测试域名部分分流差异"""
        # 国内DNS返回多个IP，国际DNS返回部分相同部分不同
        self.dispatcher.dispatch.side_effect = [
            self._make_dns_response(resolved_ips=["1.2.3.4", "2.3.4.5"]),  # 国内DNS1
            self._make_dns_response(resolved_ips=["1.2.3.4", "2.3.4.5"]),  # 国内DNS2
            self._make_dns_response(resolved_ips=["1.2.3.4", "9.9.9.9"]),  # 国际DNS1
            self._make_dns_response(resolved_ips=["1.2.3.4", "9.9.9.9"]),  # 国际DNS2
        ]

        result = await self.tester.test_domain(
            domain="www.google.com",
            domestic_dns=["114.114.114.114", "223.5.5.5"],
            international_dns=["8.8.8.8", "1.1.1.1"],
            ctx=self.ctx,
        )

        assert result.is_split is True
        assert "部分差异" in result.split_description

    @pytest.mark.asyncio
    async def test_domain_all_dns_fail(self):
        """测试所有DNS查询失败"""
        self.dispatcher.dispatch.return_value = self._make_dns_response(
            success=False
        )

        result = await self.tester.test_domain(
            domain="www.google.com",
            domestic_dns=["114.114.114.114"],
            international_dns=["8.8.8.8"],
            ctx=self.ctx,
        )

        assert result.is_split is False
        assert "解析失败" in result.split_description

    @pytest.mark.asyncio
    async def test_domain_domestic_only_fail(self):
        """测试仅国内DNS失败"""
        self.dispatcher.dispatch.side_effect = [
            self._make_dns_response(success=False),  # 国内DNS1
            self._make_dns_response(resolved_ips=["5.6.7.8"]),  # 国际DNS1
        ]

        result = await self.tester.test_domain(
            domain="www.google.com",
            domestic_dns=["114.114.114.114"],
            international_dns=["8.8.8.8"],
            ctx=self.ctx,
        )

        assert result.is_split is False
        assert "国内DNS" in result.split_description

    # ==================== 多域名测试 ====================

    @pytest.mark.asyncio
    async def test_all_domains_no_split(self):
        """测试所有域名无分流差异"""
        self.dispatcher.dispatch.return_value = self._make_dns_response(
            resolved_ips=["1.2.3.4"]
        )

        result = await self.tester.test_all_domains(
            domains=["www.google.com", "www.baidu.com"],
            domestic_dns=["114.114.114.114"],
            international_dns=["8.8.8.8"],
            ctx=self.ctx,
        )

        assert isinstance(result, DnsSplitTestResult)
        assert result.total_domains == 2
        assert result.split_count == 0
        assert len(result.split_domains) == 0
        assert len(result.domain_results) == 2
        assert result.total_duration_ms > 0

    @pytest.mark.asyncio
    async def test_all_domains_with_split(self):
        """测试部分域名存在分流差异"""
        # 第一个域名无差异，第二个域名有差异
        self.dispatcher.dispatch.side_effect = [
            self._make_dns_response(resolved_ips=["1.2.3.4"]),  # google 国内
            self._make_dns_response(resolved_ips=["1.2.3.4"]),  # google 国际
            self._make_dns_response(resolved_ips=["1.2.3.4"]),  # baidu 国内
            self._make_dns_response(resolved_ips=["5.6.7.8"]),  # baidu 国际
        ]

        result = await self.tester.test_all_domains(
            domains=["www.google.com", "www.baidu.com"],
            domestic_dns=["114.114.114.114"],
            international_dns=["8.8.8.8"],
            ctx=self.ctx,
        )

        assert result.total_domains == 2
        assert result.split_count == 1
        assert len(result.split_domains) == 1
        assert result.split_domains[0] == "www.baidu.com"

    @pytest.mark.asyncio
    async def test_all_domains_empty(self):
        """测试空域名列表"""
        result = await self.tester.test_all_domains(
            domains=[],
            domestic_dns=["114.114.114.114"],
            international_dns=["8.8.8.8"],
            ctx=self.ctx,
        )

        assert result.total_domains == 0
        assert result.split_count == 0
        assert len(result.domain_results) == 0

    # ==================== 异常处理 ====================

    @pytest.mark.asyncio
    async def test_domain_query_timeout(self):
        """测试DNS查询超时"""
        self.dispatcher.dispatch.side_effect = TimeoutError("DNS timeout")

        result = await self.tester.test_domain(
            domain="www.google.com",
            domestic_dns=["114.114.114.114"],
            international_dns=["8.8.8.8"],
            ctx=self.ctx,
        )

        assert result.is_split is False
        assert "解析失败" in result.split_description

    @pytest.mark.asyncio
    async def test_domain_query_exception(self):
        """测试DNS查询异常"""
        self.dispatcher.dispatch.side_effect = RuntimeError("Connection error")

        result = await self.tester.test_domain(
            domain="www.google.com",
            domestic_dns=["114.114.114.114"],
            international_dns=["8.8.8.8"],
            ctx=self.ctx,
        )

        assert result.is_split is False

    @pytest.mark.asyncio
    async def test_all_domains_with_exception(self):
        """测试多域名测试中的异常"""
        async def mock_dispatch(tool_name, request, ctx):
            if "baidu" in request.parameters.get("host", ""):
                raise RuntimeError("DNS server error")
            return self._make_dns_response(resolved_ips=["1.2.3.4"])

        self.dispatcher.dispatch = mock_dispatch

        result = await self.tester.test_all_domains(
            domains=["www.google.com", "www.baidu.com"],
            domestic_dns=["114.114.114.114"],
            international_dns=["8.8.8.8"],
            ctx=self.ctx,
        )

        assert result.total_domains == 2
        assert len(result.domain_results) == 2  # baidu失败但仍有结果（含错误信息）
        # baidu 的异常在 _query_single_dns 内部被捕获返回 ProbeResult，
        # test_domain 正常返回 DomainDnsResult（含错误信息）
        baidu_result = [r for r in result.domain_results if r.domain == "www.baidu.com"]
        assert len(baidu_result) == 1
        assert "ERROR:" in list(baidu_result[0].domestic_results.values())[0][0]

    # ==================== 分流检测逻辑 ====================

    def test_detect_split_no_split(self):
        """测试分流检测 - 无差异"""
        domestic = {"114": ["1.2.3.4", "5.6.7.8"]}
        international = {"8.8.8.8": ["1.2.3.4", "5.6.7.8"]}

        is_split, desc = self.tester._detect_split(
            "test.com", domestic, international
        )

        assert is_split is False
        assert "一致" in desc

    def test_detect_split_complete(self):
        """测试分流检测 - 完全差异"""
        domestic = {"114": ["1.2.3.4"]}
        international = {"8.8.8.8": ["5.6.7.8"]}

        is_split, desc = self.tester._detect_split(
            "test.com", domestic, international
        )

        assert is_split is True
        assert "完全不同" in desc

    def test_detect_split_partial(self):
        """测试分流检测 - 部分差异"""
        domestic = {"114": ["1.2.3.4", "5.6.7.8"]}
        international = {"8.8.8.8": ["1.2.3.4", "9.9.9.9"]}

        is_split, desc = self.tester._detect_split(
            "test.com", domestic, international
        )

        assert is_split is True
        assert "部分差异" in desc

    def test_detect_split_all_fail(self):
        """测试分流检测 - 全部失败"""
        domestic = {"114": ["ERROR: timeout"]}
        international = {"8.8.8.8": ["ERROR: timeout"]}

        is_split, desc = self.tester._detect_split(
            "test.com", domestic, international
        )

        assert is_split is False
        assert "解析失败" in desc

    def test_detect_split_domestic_only(self):
        """测试分流检测 - 仅国内有结果"""
        domestic = {"114": ["1.2.3.4"]}
        international = {"8.8.8.8": ["ERROR: timeout"]}

        is_split, desc = self.tester._detect_split(
            "test.com", domestic, international
        )

        assert is_split is False
        assert "国际DNS" in desc

    # ==================== RTT计算 ====================

    @pytest.mark.asyncio
    async def test_domain_rtt_calculation(self):
        """测试RTT计算"""
        self.dispatcher.dispatch.side_effect = [
            self._make_dns_response(rtt_avg=10.0, resolved_ips=["1.2.3.4"]),  # 国内
            self._make_dns_response(rtt_avg=20.0, resolved_ips=["1.2.3.4"]),  # 国内
            self._make_dns_response(rtt_avg=200.0, resolved_ips=["1.2.3.4"]),  # 国际
            self._make_dns_response(rtt_avg=300.0, resolved_ips=["1.2.3.4"]),  # 国际
        ]

        result = await self.tester.test_domain(
            domain="www.google.com",
            domestic_dns=["114.114.114.114", "223.5.5.5"],
            international_dns=["8.8.8.8", "1.1.1.1"],
            ctx=self.ctx,
        )

        assert result.domestic_avg_rtt_ms == 15.0  # (10+20)/2
        assert result.international_avg_rtt_ms == 250.0  # (200+300)/2
