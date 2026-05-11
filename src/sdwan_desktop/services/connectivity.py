"""
连通性测试服务 - 探测目标配置与连通性测试

提供网关连通性、DNS解析、国内外目标连通性测试功能。
使用 ToolDispatcher 调用底层探测工具，返回结构化 ProbeResult。

遵循 SDWAN_SPEC.md §2.4 工具系统规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.probe import (
    ProbeMetric,
    ProbeProtocol,
    ProbeResult,
    ProbeStatus,
    ProbeTarget,
)
from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.tools.registry.base import ToolDispatcher

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConnectivityTestResult:
    """连通性测试结果聚合

    包含网关、DNS、国内外目标的所有探测结果及统计信息。
    """

    gateway_ping: Optional[ProbeResult] = None
    """网关连通性探测结果"""

    domestic_dns_results: List[ProbeResult] = field(default_factory=list)
    """国内DNS服务器探测结果列表"""

    international_dns_results: List[ProbeResult] = field(default_factory=list)
    """国际DNS服务器探测结果列表"""

    domestic_target_results: List[ProbeResult] = field(default_factory=list)
    """国内目标连通性探测结果列表"""

    international_target_results: List[ProbeResult] = field(default_factory=list)
    """国际目标连通性探测结果列表"""

    domestic_success_rate: float = 0.0
    """国内目标成功率 (0-1)"""

    international_success_rate: float = 0.0
    """国际目标成功率 (0-1)"""

    total_duration_ms: float = 0.0
    """总耗时(毫秒)"""

    errors: List[str] = field(default_factory=list)
    """采集过程中的错误信息列表"""


class ConnectivityTester:
    """连通性测试器

    通过 ToolDispatcher 调用 ping/tcping/http 等工具，
    对网关、DNS服务器、国内外目标进行连通性探测。

    使用 asyncio.Semaphore 限制最大并发数。
    """

    def __init__(
        self,
        dispatcher: Optional[ToolDispatcher] = None,
        max_concurrent: int = 5,
        probe_interval: float = 0.5,
    ):
        """初始化连通性测试器

        Args:
            dispatcher: 工具调度器，如果为None则创建新实例
            max_concurrent: 最大并发探测数
            probe_interval: 探测间隔(秒)
        """
        self.dispatcher = dispatcher or ToolDispatcher()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.probe_interval = probe_interval

    async def test_gateway(
        self, gateway_ip: str, ctx: FlowContext
    ) -> ProbeResult:
        """测试默认网关连通性

        使用ICMP协议对网关进行4次ping探测。

        Args:
            gateway_ip: 网关IP地址
            ctx: 流程上下文

        Returns:
            ProbeResult: 网关探测结果
        """
        target = ProbeTarget(
            host=gateway_ip,
            protocol=ProbeProtocol.ICMP,
            count=4,
            timeout_seconds=10,
        )

        return await self._execute_probe(target, ctx)

    async def test_domestic_dns(
        self, dns_servers: List[str], ctx: FlowContext
    ) -> List[ProbeResult]:
        """测试国内DNS服务器连通性

        对多个国内DNS服务器并发进行DNS探测。

        Args:
            dns_servers: 国内DNS服务器IP列表
            ctx: 流程上下文

        Returns:
            List[ProbeResult]: DNS探测结果列表
        """
        targets = [
            ProbeTarget(
                host=dns,
                protocol=ProbeProtocol.DNS,
                count=2,
                timeout_seconds=5,
                dns_server=dns,
            )
            for dns in dns_servers
        ]

        return await self._execute_probes_concurrent(targets, ctx)

    async def test_international_dns(
        self, dns_servers: List[str], ctx: FlowContext
    ) -> List[ProbeResult]:
        """测试国际DNS服务器连通性

        对多个国际DNS服务器并发进行DNS探测。

        Args:
            dns_servers: 国际DNS服务器IP列表
            ctx: 流程上下文

        Returns:
            List[ProbeResult]: DNS探测结果列表
        """
        targets = [
            ProbeTarget(
                host=dns,
                protocol=ProbeProtocol.DNS,
                count=2,
                timeout_seconds=5,
                dns_server=dns,
            )
            for dns in dns_servers
        ]

        return await self._execute_probes_concurrent(targets, ctx)

    async def test_domestic_targets(
        self, targets_config: List[Dict[str, Any]], ctx: FlowContext
    ) -> List[ProbeResult]:
        """测试国内目标连通性

        对配置的国内目标（HTTP/ICMP）进行连通性探测。

        Args:
            targets_config: 目标配置列表，每项包含 host 和 type
            ctx: 流程上下文

        Returns:
            List[ProbeResult]: 探测结果列表
        """
        targets = self._build_targets_from_config(targets_config)
        return await self._execute_probes_concurrent(targets, ctx)

    async def test_international_targets(
        self, targets_config: List[Dict[str, Any]], ctx: FlowContext
    ) -> List[ProbeResult]:
        """测试国际目标连通性

        对配置的国际目标（HTTP/ICMP）进行连通性探测。

        Args:
            targets_config: 目标配置列表，每项包含 host 和 type
            ctx: 流程上下文

        Returns:
            List[ProbeResult]: 探测结果列表
        """
        targets = self._build_targets_from_config(targets_config)
        return await self._execute_probes_concurrent(targets, ctx)

    async def test_all(
        self,
        gateway_ip: str,
        domestic_dns: List[str],
        international_dns: List[str],
        domestic_targets: List[Dict[str, Any]],
        international_targets: List[Dict[str, Any]],
        ctx: FlowContext,
    ) -> ConnectivityTestResult:
        """执行全部连通性测试

        按以下顺序执行：
        1. 网关连通性测试
        2. 国内DNS测试（与网关测试并行）
        3. 国际DNS测试（与网关测试并行）
        4. 国内目标测试
        5. 国际目标测试

        Args:
            gateway_ip: 网关IP地址
            domestic_dns: 国内DNS服务器列表
            international_dns: 国际DNS服务器列表
            domestic_targets: 国内目标配置列表
            international_targets: 国际目标配置列表
            ctx: 流程上下文

        Returns:
            ConnectivityTestResult: 聚合的连通性测试结果
        """
        import time

        start_time = time.monotonic()
        result = ConnectivityTestResult()
        logger.info(
            "开始执行全部连通性测试",
            extra={"trace_id": ctx.trace_id},
        )

        try:
            # 阶段1: 并行执行网关测试和DNS测试
            gateway_task = self.test_gateway(gateway_ip, ctx)
            domestic_dns_task = self.test_domestic_dns(domestic_dns, ctx)
            international_dns_task = self.test_international_dns(
                international_dns, ctx
            )

            phase1_results = await asyncio.gather(
                gateway_task,
                domestic_dns_task,
                international_dns_task,
                return_exceptions=True,
            )

            # 处理阶段1结果
            gw_result = phase1_results[0]
            if isinstance(gw_result, Exception):
                logger.error(
                    f"网关测试异常: {gw_result}",
                    extra={"trace_id": ctx.trace_id},
                )
                result.errors.append(f"网关测试失败: {gw_result}")
                result.gateway_ping = ProbeResult(
                    target=ProbeTarget(host=gateway_ip, protocol=ProbeProtocol.ICMP),
                    status=ProbeStatus.FAILED,
                    success=False,
                    error_message=str(gw_result),
                )
            else:
                result.gateway_ping = gw_result

            ddns_result = phase1_results[1]
            if isinstance(ddns_result, Exception):
                logger.error(
                    f"国内DNS测试异常: {ddns_result}",
                    extra={"trace_id": ctx.trace_id},
                )
                result.errors.append(f"国内DNS测试失败: {ddns_result}")
            else:
                result.domestic_dns_results = ddns_result

            idns_result = phase1_results[2]
            if isinstance(idns_result, Exception):
                logger.error(
                    f"国际DNS测试异常: {idns_result}",
                    extra={"trace_id": ctx.trace_id},
                )
                result.errors.append(f"国际DNS测试失败: {idns_result}")
            else:
                result.international_dns_results = idns_result

            # 阶段2: 并行执行国内外目标测试
            domestic_task = self.test_domestic_targets(domestic_targets, ctx)
            international_task = self.test_international_targets(
                international_targets, ctx
            )

            phase2_results = await asyncio.gather(
                domestic_task,
                international_task,
                return_exceptions=True,
            )

            # 处理阶段2结果
            domestic_result = phase2_results[0]
            if isinstance(domestic_result, Exception):
                logger.error(
                    f"国内目标测试异常: {domestic_result}",
                    extra={"trace_id": ctx.trace_id},
                )
                result.errors.append(f"国内目标测试失败: {domestic_result}")
            else:
                result.domestic_target_results = domestic_result

            international_result = phase2_results[1]
            if isinstance(international_result, Exception):
                logger.error(
                    f"国际目标测试异常: {international_result}",
                    extra={"trace_id": ctx.trace_id},
                )
                result.errors.append(f"国际目标测试失败: {international_result}")
            else:
                result.international_target_results = international_result

            # 计算成功率
            result.domestic_success_rate = self._calculate_success_rate(
                result.domestic_target_results
            )
            result.international_success_rate = self._calculate_success_rate(
                result.international_target_results
            )

        except Exception as e:
            logger.error(
                f"连通性测试整体异常: {e}",
                extra={"trace_id": ctx.trace_id},
            )
            result.errors.append(f"连通性测试整体异常: {e}")

        result.total_duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            f"连通性测试完成: 国内成功率={result.domestic_success_rate:.1%}, "
            f"国际成功率={result.international_success_rate:.1%}, "
            f"耗时={result.total_duration_ms:.0f}ms",
            extra={"trace_id": ctx.trace_id},
        )

        return result

    # ==================== 内部方法 ====================

    def _build_targets_from_config(
        self, targets_config: List[Dict[str, Any]]
    ) -> List[ProbeTarget]:
        """从配置构建探测目标列表

        Args:
            targets_config: 目标配置列表，每项包含 host 和 type

        Returns:
            List[ProbeTarget]: 探测目标列表
        """
        targets = []
        for item in targets_config:
            host = item.get("host", "")
            probe_type = item.get("type", "icmp").lower()

            if probe_type == "icmp":
                protocol = ProbeProtocol.ICMP
                timeout = 10
            elif probe_type == "http":
                protocol = ProbeProtocol.HTTP
                timeout = 15
            elif probe_type == "https":
                protocol = ProbeProtocol.HTTPS
                timeout = 15
            elif probe_type == "tcp":
                protocol = ProbeProtocol.TCP
                timeout = 10
            else:
                protocol = ProbeProtocol.ICMP
                timeout = 10

            targets.append(
                ProbeTarget(
                    host=host,
                    protocol=protocol,
                    count=3,
                    timeout_seconds=timeout,
                )
            )
        return targets

    async def _execute_probe(
        self, target: ProbeTarget, ctx: FlowContext
    ) -> ProbeResult:
        """执行单次探测

        根据目标协议类型调用对应的工具。

        Args:
            target: 探测目标
            ctx: 流程上下文

        Returns:
            ProbeResult: 探测结果
        """
        tool_name = self._get_tool_name(target.protocol)
        if not tool_name:
            return ProbeResult(
                target=target,
                status=ProbeStatus.FAILED,
                success=False,
                error_message=f"不支持的探测协议: {target.protocol}",
            )

        request = ToolRequest(
            tool_name=tool_name,
            parameters={
                "host": target.host,
                "count": target.count,
                "timeout": target.timeout_seconds,
            },
            trace_id=ctx.trace_id,
        )

        # DNS探测需要额外参数
        if target.protocol == ProbeProtocol.DNS and target.dns_server:
            request.parameters["dns_server"] = target.dns_server
            # DNS 探测需要一个目标域名来执行查询，默认使用 www.baidu.com 作为探针
            if "domain" not in request.parameters:
                request.parameters["domain"] = target.host or "www.baidu.com"

        # TCP/HTTP/HTTPS探测都需要端口
        if target.protocol in (ProbeProtocol.TCP, ProbeProtocol.HTTP, ProbeProtocol.HTTPS):
            request.parameters["port"] = target.port or (
                443 if target.protocol == ProbeProtocol.HTTPS else 80
            )

        # 2. 通过调度器调用工具
        try:
            tool_name = self._get_tool_name(target.protocol)
            if not tool_name:
                return ProbeResult(
                    target=target,
                    status=ProbeStatus.FAILED,
                    success=False,
                    error_message=f"不支持的探测协议: {target.protocol}",
                )

            response: ToolResponse = await self.dispatcher.dispatch(
                tool_name=tool_name,
                request=request,
                ctx=ctx,
            )

            if response.success and response.data:
                return self._convert_to_probe_result(target, response)
            else:
                return ProbeResult(
                    target=target,
                    status=ProbeStatus.FAILED,
                    success=False,
                    error_message=response.error_message or "探测失败",
                    error_code=response.error_code,
                    duration_ms=response.duration_ms,
                )

        except asyncio.TimeoutError:
            logger.warning(
                f"探测超时: {target.host}",
                extra={"trace_id": ctx.trace_id},
            )
            return ProbeResult(
                target=target,
                status=ProbeStatus.TIMEOUT,
                success=False,
                error_message=f"探测 {target.host} 超时",
            )
        except Exception as e:
            logger.error(
                f"探测异常: {target.host} - {e}",
                extra={"trace_id": ctx.trace_id},
            )
            return ProbeResult(
                target=target,
                status=ProbeStatus.FAILED,
                success=False,
                error_message=str(e),
            )

    async def _execute_probes_concurrent(
        self, targets: List[ProbeTarget], ctx: FlowContext
    ) -> List[ProbeResult]:
        """并发执行多个探测

        使用 asyncio.gather 和 Semaphore 控制并发数。

        Args:
            targets: 探测目标列表
            ctx: 流程上下文

        Returns:
            List[ProbeResult]: 探测结果列表
        """
        if not targets:
            return []

        async def limited_probe(target: ProbeTarget) -> ProbeResult:
            """带并发限制的探测"""
            async with self.semaphore:
                result = await self._execute_probe(target, ctx)
                # 探测间隔
                if self.probe_interval > 0:
                    await asyncio.sleep(self.probe_interval)
                return result

        results = await asyncio.gather(
            *[limited_probe(t) for t in targets],
            return_exceptions=True,
        )

        # 处理异常结果
        processed: List[ProbeResult] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(
                    f"并发探测异常 ({targets[i].host}): {r}",
                    extra={"trace_id": ctx.trace_id},
                )
                processed.append(
                    ProbeResult(
                        target=targets[i],
                        status=ProbeStatus.FAILED,
                        success=False,
                        error_message=str(r),
                    )
                )
            else:
                processed.append(r)

        return processed

    def _convert_to_probe_result(
        self, target: ProbeTarget, response: ToolResponse
    ) -> ProbeResult:
        """将工具响应转换为 ProbeResult

        遵循 PATCH-002: 在边界处将dict转换为结构化对象。

        Args:
            target: 原始探测目标
            response: 工具响应

        Returns:
            ProbeResult: 结构化的探测结果
        """
        data = response.data or {}

        # 构建指标 - 兼容不同工具的字段命名
        metrics = ProbeMetric(
            rtt_min=data.get("rtt_min"),
            rtt_avg=data.get("rtt_avg") or data.get("response_time_ms"),
            rtt_max=data.get("rtt_max"),
            rtt_stddev=data.get("rtt_stddev"),
            loss_rate=data.get("loss_rate"),
            ttl=data.get("ttl"),
            resolved_ips=data.get("resolved_ips", []),
            response_code=data.get("response_code"),
        )

        # 确定状态
        status = ProbeStatus.SUCCESS if response.success else ProbeStatus.FAILED
        if response.error_code == "TOOL_TIMEOUT":
            status = ProbeStatus.TIMEOUT

        return ProbeResult(
            target=target,
            status=status,
            success=response.success,
            raw_output=data.get("raw_output"),
            metrics=metrics,
            error_message=response.error_message,
            error_code=response.error_code,
            duration_ms=response.duration_ms,
        )

    def _get_tool_name(self, protocol: ProbeProtocol) -> Optional[str]:
        """根据协议获取对应的工具名称

        Args:
            protocol: 探测协议

        Returns:
            Optional[str]: 工具名称，不支持的协议返回None
        """
        tool_map = {
            ProbeProtocol.ICMP: "ping",
            ProbeProtocol.TCP: "tcping",
            ProbeProtocol.DNS: "dns",
            ProbeProtocol.HTTP: "tcping",
            ProbeProtocol.HTTPS: "tcping",
        }
        return tool_map.get(protocol)

    def _calculate_success_rate(
        self, results: List[ProbeResult]
    ) -> float:
        """计算探测成功率

        Args:
            results: 探测结果列表

        Returns:
            float: 成功率 (0-1)
        """
        if not results:
            return 0.0

        success_count = sum(1 for r in results if r.success)
        return success_count / len(results)

    async def test_internet_optimized(
        self,
        domains: List[str] = None,
        ctx: Optional[FlowContext] = None,
        use_cache: bool = True,
    ) -> ConnectivityTestResult:
        """优化的互联网连通性测试（支持结果缓存和复用）

        优化策略：
        1. 使用统一的域名目标集
        2. 检查 Context 中是否有 DNS 解析缓存，避免重复查询
        3. 将 TCPing 结果存入 Context，供后续步骤复用

        Args:
            domains: 测试域名列表（默认使用统一域名集）
            ctx: 流程上下文
            use_cache: 是否使用缓存（默认True）

        Returns:
            ConnectivityTestResult: 互联网连通性测试结果
        """
        from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS
        
        # ✅ 使用统一域名集
        if domains is None:
            domains = DEFAULT_TEST_DOMAINS
        
        if not ctx:
            import uuid
            ctx = FlowContext(trace_id=str(uuid.uuid4()))
        
        # ✅ 检查 DNS 解析缓存
        dns_cache_dict = ctx.get("dns_resolution_cache") if use_cache else None
        if dns_cache_dict:
            logger.info(
                f"使用DNS解析缓存，跳过重复查询: {len(dns_cache_dict)}个域名已缓存",
                extra={"trace_id": ctx.trace_id}
            )
        
        # ✅ 按需求：从统一域名集中分类（baidu=国内，youtube/tiktok=国际）
        domestic_domains = []
        international_domains = []
        
        for domain in domains:
            # 国内域名判断：包含.cn或明确是国内服务
            if ".cn" in domain or any(x in domain for x in ["baidu", "taobao", "jd", "qq", "aliyun"]):
                domestic_domains.append(domain)
            # 国际域名判断：其他都视为国际（包括youtube、tiktok、google等）
            else:
                international_domains.append(domain)
        
        # 如果分类后某一类为空，记录警告
        if not domestic_domains:
            logger.warning(f"未检测到国内域名，domains={domains}", extra={"trace_id": ctx.trace_id})
        if not international_domains:
            logger.warning(f"未检测到国际域名，domains={domains}", extra={"trace_id": ctx.trace_id})
        
        result = ConnectivityTestResult()
        
        # 并发执行国内和国际目标测试
        domestic_tasks = []
        for domain in domestic_domains:
            # 使用 TCPing 测试 443 端口（HTTPS）
            target = ProbeTarget(
                host=domain,
                protocol=ProbeProtocol.TCP,
                port=443,
                count=2,
                timeout_seconds=10,
            )
            domestic_tasks.append(self._execute_probe(target, ctx))
        
        international_tasks = []
        for domain in international_domains:
            # 使用 TCPing 测试 443 端口（HTTPS）
            target = ProbeTarget(
                host=domain,
                protocol=ProbeProtocol.TCP,
                port=443,
                count=2,
                timeout_seconds=10,
            )
            international_tasks.append(self._execute_probe(target, ctx))
        
        # 并发执行所有探测
        all_results = await asyncio.gather(
            *domestic_tasks,
            *international_tasks,
            return_exceptions=True
        )
        
        # 分离国内和国际结果
        domestic_results = []
        international_results = []
        
        for i, res in enumerate(all_results):
            if isinstance(res, Exception):
                error_result = ProbeResult(
                    target=ProbeTarget(host=domains[i] if i < len(domains) else "unknown", protocol=ProbeProtocol.TCP),
                    status=ProbeStatus.FAILED,
                    success=False,
                    error_message=str(res)
                )
                if i < len(domestic_tasks):
                    domestic_results.append(error_result)
                else:
                    international_results.append(error_result)
            else:
                if i < len(domestic_tasks):
                    domestic_results.append(res)
                else:
                    international_results.append(res)
        
        result.domestic_target_results = domestic_results
        result.international_target_results = international_results
        result.domestic_success_rate = self._calculate_success_rate(domestic_results)
        result.international_success_rate = self._calculate_success_rate(international_results)
        
        # ✅ 将 TCPing 结果转换为结构化缓存并存入 Context
        tcping_cache_entries: Dict[str, Any] = {}
        for domain_result in domestic_results + international_results:
            domain = domain_result.target.host
            tcping_cache_entries[domain] = {
                "success": domain_result.success,
                "rtt_avg": domain_result.metrics.rtt_avg if domain_result.metrics else None,
                "loss_rate": domain_result.metrics.loss_rate if domain_result.metrics else None,
            }
        
        ctx.set("tcping_results_cache", tcping_cache_entries)
        
        logger.info(
            f"TCPing结果已缓存到Context（{len(tcping_cache_entries)}个域名），可供后续步骤复用",
            extra={"trace_id": ctx.trace_id}
        )
        
        return result
