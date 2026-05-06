"""
DNS分流测试服务 - 对比国内外DNS解析差异

测试同一域名在不同DNS服务器下的解析结果，判断是否存在DNS分流异常。
使用 ToolDispatcher 调用 dns_lookup 工具进行DNS查询。

遵循 SDWAN_SPEC.md §2.4 工具系统规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
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
class DomainDnsResult:
    """单个域名的DNS分流测试结果"""

    domain: str
    """测试域名"""

    domestic_results: Dict[str, Any] = field(default_factory=dict)
    """国内DNS解析结果 {dns_server: resolved_ips}"""

    international_results: Dict[str, Any] = field(default_factory=dict)
    """国际DNS解析结果 {dns_server: resolved_ips}"""

    is_split: bool = False
    """是否存在DNS分流差异"""

    split_description: str = ""
    """分流差异描述"""

    domestic_avg_rtt_ms: float = 0.0
    """国内DNS平均响应时间(ms)"""

    international_avg_rtt_ms: float = 0.0
    """国际DNS平均响应时间(ms)"""


@dataclass(slots=True)
class DnsSplitTestResult:
    """DNS分流测试结果聚合"""

    domain_results: List[DomainDnsResult] = field(default_factory=list)
    """各域名测试结果列表"""

    split_domains: List[str] = field(default_factory=list)
    """存在分流差异的域名列表"""

    total_domains: int = 0
    """测试域名总数"""

    split_count: int = 0
    """存在分流差异的域名数"""

    total_duration_ms: float = 0.0
    """总耗时(毫秒)"""

    errors: List[str] = field(default_factory=list)
    """测试过程中的错误信息"""


@dataclass(slots=True)
class TracerouteHopInfo:
    """Traceroute 单跳信息"""
    
    hop_number: int = 0
    """跳数"""
    
    ip_addresses: List[str] = field(default_factory=list)
    """该跳的IP地址列表（可能有多个响应）"""
    
    rtts: List[float] = field(default_factory=list)
    """往返时间列表（毫秒）"""
    
    is_timeout: bool = False
    """是否超时"""


@dataclass(slots=True)
class DomainPathAnalysisResult:
    """单个域名的路径分析结果"""

    domain: str = ""
    """目标域名"""
    
    resolved_ip: str = "N/A"
    """解析后的IP地址"""
    
    full_path: List[TracerouteHopInfo] = field(default_factory=list)
    """完整路径（所有跳）"""
    
    cpe_exit_hop: int = 2
    """CPE出口跳数（通常第2跳是CPE，从第3跳开始分流）"""
    
    post_cpe_hops: List[TracerouteHopInfo] = field(default_factory=list)
    """CPE之后的路径（用于分析分流）"""
    
    path_fingerprint: str = ""
    """路径指纹（用于快速比对，如 "8.1.3.1->5.1.1.2"）"""
    
    link_category: str = "unknown"
    """链路分类: domestic/international/unknown"""
    
    confidence: float = 0.0
    """路径识别置信度 (0-1)"""


@dataclass(slots=True)
class CpeLinkRouteResult:
    """CPE链路分流检测结果（按域名维度）"""

    domain_results: List[DomainPathAnalysisResult] = field(default_factory=list)
    """各域名的路径分析结果"""

    detected_links: List[str] = field(default_factory=list)
    """检测到的不同链路标识列表（基于路径指纹）"""

    link_distribution: Dict[str, List[str]] = field(default_factory=dict)
    """链路分布统计 {link_fingerprint: [domain1, domain2, ...]}"""

    is_multi_link: bool = False
    """是否存在多链路分流"""

    multi_link_count: int = 0
    """使用的不同链路数量"""

    total_domains_tested: int = 0
    """测试的域名总数"""

    total_duration_ms: float = 0.0
    """总耗时(毫秒)"""

    errors: List[str] = field(default_factory=list)
    """测试过程中的错误或警告信息"""


class DnsSplitTester:
    """DNS分流测试器

    对比国内外DNS服务器对同一域名的解析结果，
    判断是否存在DNS分流异常（如DNS劫持、解析不一致等）。

    使用 asyncio.Semaphore 限制最大并发数。
    """

    def __init__(
        self,
        dispatcher: Optional[ToolDispatcher] = None,
        max_concurrent: int = 3,
    ):
        """初始化DNS分流测试器

        Args:
            dispatcher: 工具调度器，如果为None则创建新实例
            max_concurrent: 最大并发DNS查询数
        """
        self.dispatcher = dispatcher or ToolDispatcher()
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def test_domain(
        self,
        domain: str,
        domestic_dns: List[str],
        international_dns: List[str],
        ctx: FlowContext,
    ) -> DomainDnsResult:
        """测试单个域名的DNS分流情况

        对指定域名分别在国内外DNS服务器上进行解析，
        对比解析结果判断是否存在分流异常。

        Args:
            domain: 要测试的域名
            domestic_dns: 国内DNS服务器列表
            international_dns: 国际DNS服务器列表
            ctx: 流程上下文

        Returns:
            DomainDnsResult: 域名DNS测试结果
        """
        result = DomainDnsResult(domain=domain)

        # 并发查询所有DNS服务器
        all_dns = []
        for dns in domestic_dns:
            all_dns.append(("domestic", dns))
        for dns in international_dns:
            all_dns.append(("international", dns))

        async def query_dns(
            category: str, dns_server: str
        ) -> tuple:
            """查询单个DNS服务器"""
            probe_result = await self._query_single_dns(
                domain, dns_server, ctx
            )
            return category, dns_server, probe_result

        tasks = [query_dns(cat, dns) for cat, dns in all_dns]
        query_results = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        # 处理查询结果
        domestic_rtts: List[float] = []
        international_rtts: List[float] = []

        for qr in query_results:
            if isinstance(qr, Exception):
                logger.error(
                    f"DNS查询异常 ({domain}): {qr}",
                    extra={"trace_id": ctx.trace_id},
                )
                result.split_description += f"DNS查询异常: {qr}; "
                continue

            category, dns_server, probe_result = qr

            if probe_result.success:
                resolved_ips = probe_result.metrics.resolved_ips
                rtt = probe_result.metrics.rtt_avg or 0.0

                if category == "domestic":
                    result.domestic_results[dns_server] = resolved_ips
                    domestic_rtts.append(rtt)
                else:
                    result.international_results[dns_server] = resolved_ips
                    international_rtts.append(rtt)
            else:
                error_msg = probe_result.error_message or "查询失败"
                if category == "domestic":
                    result.domestic_results[dns_server] = [f"ERROR: {error_msg}"]
                else:
                    result.international_results[dns_server] = [f"ERROR: {error_msg}"]

        # 计算平均RTT
        if domestic_rtts:
            result.domestic_avg_rtt_ms = sum(domestic_rtts) / len(domestic_rtts)
        if international_rtts:
            result.international_avg_rtt_ms = (
                sum(international_rtts) / len(international_rtts)
            )

        # 判断是否存在分流差异
        result.is_split, result.split_description = self._detect_split(
            domain,
            result.domestic_results,
            result.international_results,
        )

        return result

    async def test_all_domains(
        self,
        domains: List[str],
        domestic_dns: List[str],
        international_dns: List[str],
        ctx: FlowContext,
    ) -> DnsSplitTestResult:
        """测试所有域名的DNS分流情况

        对多个域名并发进行DNS分流测试。

        Args:
            domains: 要测试的域名列表
            domestic_dns: 国内DNS服务器列表
            international_dns: 国际DNS服务器列表
            ctx: 流程上下文

        Returns:
            DnsSplitTestResult: DNS分流测试结果聚合
        """
        import time

        start_time = time.monotonic()
        result = DnsSplitTestResult(total_domains=len(domains))

        logger.info(
            f"开始DNS分流测试: {len(domains)}个域名",
            extra={"trace_id": ctx.trace_id},
        )

        if not domains:
            logger.warning(
                "没有需要测试的域名",
                extra={"trace_id": ctx.trace_id},
            )
            return result

        async def limited_test(domain: str) -> DomainDnsResult:
            """带并发限制的域名测试"""
            async with self.semaphore:
                return await self.test_domain(
                    domain, domestic_dns, international_dns, ctx
                )

        domain_results = await asyncio.gather(
            *[limited_test(d) for d in domains],
            return_exceptions=True,
        )

        # 处理结果
        for i, dr in enumerate(domain_results):
            if isinstance(dr, Exception):
                logger.error(
                    f"域名测试异常 ({domains[i]}): {dr}",
                    extra={"trace_id": ctx.trace_id},
                )
                result.errors.append(f"域名 {domains[i]} 测试失败: {dr}")
                continue

            result.domain_results.append(dr)
            if dr.is_split:
                result.split_domains.append(dr.domain)
                result.split_count += 1

        result.total_duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            f"DNS分流测试完成: {result.total_domains}个域名, "
            f"{result.split_count}个存在分流差异, "
            f"耗时={result.total_duration_ms:.0f}ms",
            extra={"trace_id": ctx.trace_id},
        )

        return result

    # ==================== 内部方法 ====================

    async def _query_single_dns(
        self, domain: str, dns_server: str, ctx: FlowContext
    ) -> ProbeResult:
        """查询单个DNS服务器

        Args:
            domain: 要查询的域名
            dns_server: DNS服务器IP
            ctx: 流程上下文

        Returns:
            ProbeResult: DNS查询结果
        """
        target = ProbeTarget(
            host=domain,
            protocol=ProbeProtocol.DNS,
            count=1,
            timeout_seconds=5,
            dns_server=dns_server,
        )

        request = ToolRequest(
            tool_name="dns_lookup",
            parameters={
                "domain": domain,  # 修正参数名为 domain
                "dns_server": dns_server,
                "timeout": 5,
            },
            trace_id=ctx.trace_id,
        )

        # 2. 通过调度器调用工具
        try:
            response: ToolResponse = await self.dispatcher.dispatch(
                tool_name="dns",  # 修正工具名称为 dns
                request=request,
                ctx=ctx,
            )

            if response.success and response.data:
                data = response.data
                metrics = ProbeMetric(
                    rtt_avg=data.get("rtt_avg"),
                    resolved_ips=data.get("resolved_ips", []),
                    response_code=data.get("response_code"),
                )

                return ProbeResult(
                    target=target,
                    status=ProbeStatus.SUCCESS,
                    success=True,
                    metrics=metrics,
                    duration_ms=response.duration_ms,
                )
            else:
                return ProbeResult(
                    target=target,
                    status=ProbeStatus.FAILED,
                    success=False,
                    error_message=response.error_message or "DNS查询失败",
                    error_code=response.error_code,
                    duration_ms=response.duration_ms,
                )

        except asyncio.TimeoutError:
            logger.warning(
                f"DNS查询超时: {domain} @ {dns_server}",
                extra={"trace_id": ctx.trace_id},
            )
            return ProbeResult(
                target=target,
                status=ProbeStatus.TIMEOUT,
                success=False,
                error_message=f"DNS查询超时: {domain} @ {dns_server}",
            )
        except Exception as e:
            logger.error(
                f"DNS查询异常: {domain} @ {dns_server} - {e}",
                extra={"trace_id": ctx.trace_id},
            )
            return ProbeResult(
                target=target,
                status=ProbeStatus.FAILED,
                success=False,
                error_message=str(e),
            )

    def _detect_split(
        self,
        domain: str,
        domestic_results: Dict[str, List[str]],
        international_results: Dict[str, List[str]],
    ) -> tuple:
        """检测DNS分流差异

        核心逻辑：基于“出口-服务器”维度的交叉对比。
        1. **同服务器跨出口对比**：同一 DNS（如 8.8.8.8）在国内外出口下解析结果不同，说明链路存在分流。
        2. **同出口跨服务器对比**：同一出口下，不同 DNS 解析结果不同，属于正常 CDN 调度或 DNS 差异。
        3. **综合判定**：只要发现任意一个 DNS 服务器在不同出口下的解析集合存在显著差异（独有 IP），即判定为分流。

        Args:
            domain: 域名
            domestic_results: 国内出口下的解析结果 {dns_server: [ips]}
            international_results: 国际出口下的解析结果 {dns_server: [ips]}

        Returns:
            tuple: (is_split, description)
        """
        # 收集所有解析到的IP（过滤掉错误信息）
        domestic_ips = set()
        for ips in domestic_results.values():
            for ip in ips:
                if isinstance(ip, str) and not ip.startswith("ERROR:"):
                    domestic_ips.add(ip)

        international_ips = set()
        for ips in international_results.values():
            for ip in ips:
                if isinstance(ip, str) and not ip.startswith("ERROR:"):
                    international_ips.add(ip)

        # 基础校验
        if not domestic_ips and not international_ips:
            return False, f"域名 {domain} 在所有DNS服务器上均解析失败"

        if not domestic_ips:
            return True, f"域名 {domain} 在国内出口下解析失败（链路阻断或路由异常）"

        if not international_ips:
            return True, f"域名 {domain} 在国际出口下解析失败（可能被墙或DNS污染）"

        # 深度分流判定：检查是否存在“出口敏感型”DNS服务器
        all_dns_servers = set(domestic_results.keys()) | set(international_results.keys())
        split_evidence = []

        for dns in all_dns_servers:
            dom_set = set(ip for ip in domestic_results.get(dns, []) if not ip.startswith("ERROR:"))
            int_set = set(ip for ip in international_results.get(dns, []) if not ip.startswith("ERROR:"))
            
            if not dom_set or not int_set:
                continue

            # 如果同一个 DNS 在不同出口下返回了不同的 IP 集合
            if dom_set != int_set:
                only_dom = dom_set - int_set
                only_int = int_set - dom_set
                evidence_parts = []
                if only_dom: evidence_parts.append(f"国内独有:{only_dom}")
                if only_int: evidence_parts.append(f"国际独有:{only_int}")
                
                split_evidence.append(f"[{dns}] " + ", ".join(evidence_parts))

        # 只要有证据表明链路影响了 DNS 结果，即判定为分流
        if split_evidence:
            return True, f"域名 {domain} 检测到链路分流: {'; '.join(split_evidence)}"

        # 兜底逻辑：如果每个 DNS 单独看都一样，但不同 DNS 之间在不同出口有差异
        # （这种情况较少见，通常意味着复杂的 CDN 调度）
        only_domestic_total = domestic_ips - international_ips
        only_international_total = international_ips - domestic_ips
        
        if only_domestic_total or only_international_total:
            return True, f"域名 {domain} 存在全局性解析差异: 国内独有={only_domestic_total}, 国际独有={only_international_total}"

        return False, f"域名 {domain} 在各出口及DNS下解析结果一致"

    def _classify_link_type(self, fingerprint_ips: List[str]) -> str:
        """根据路径指纹IP初步判断链路类型
        
        Args:
            fingerprint_ips: 路径指纹中的IP地址列表
            
        Returns:
            链路类型分类字符串
        """
        if not fingerprint_ips:
            return "unknown"
        
        # 简单的基于IP段的分类逻辑
        for ip in fingerprint_ips:
            # 私有地址段
            if ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172."):
                return "private_network"
            # 常见的运营商网段（简化判断）
            elif ip.startswith("100.") or ip.startswith("101."):
                return "carrier_network"
            # 公网地址
            else:
                return "public_internet"
        
        return "mixed"

    def _group_by_path_fingerprint(self, domain_results: List[DomainPathAnalysisResult]) -> Dict[str, List[str]]:
        """根据路径指纹对域名进行链路分组
        
        Args:
            domain_results: 所有域名的路径分析结果列表
            
        Returns:
            链路分组的字典 {path_fingerprint: [domain1, domain2, ...]}
        """
        link_groups = {}
        
        for dr in domain_results:
            fingerprint = dr.path_fingerprint
            
            # 优化：如果指纹是"无有效跳点"或"traceroute异常"，使用更友好的描述
            if not fingerprint or fingerprint == "unknown":
                fingerprint = "路径不可达"
            elif fingerprint.startswith("traceroute异常"):
                fingerprint = "检测失败"
            
            if fingerprint not in link_groups:
                link_groups[fingerprint] = []
            
            link_groups[fingerprint].append(dr.domain)
        
        return link_groups

    async def test_cpe_link_routing(
        self,
        domains: List[str] = None,
        max_hops: int = 6,  # 优化：默认仅追踪6跳，足够识别CPE后的链路差异
        cpe_exit_hop: int = 2,
        ctx: Optional[FlowContext] = None,
    ) -> CpeLinkRouteResult:
        """检测CPE设备对不同目标域名的链路分流情况

        核心逻辑：通过对多个国内外域名执行 traceroute，分析 CPE 之后（第3跳起）的路径差异，
        判断 CPE 是否根据目标地址将流量分发到不同的物理/逻辑链路。

        检测步骤：
        1. 对每个目标域名执行 DNS 解析获取目标 IP
        2. 对每个目标 IP 执行 traceroute（限制跳数以提高效率）
        3. 提取 CPE 之后的路径（跳过前2跳：客户端→网关→CPE）
        4. 生成路径指纹并对比，识别不同的出口链路
        5. 统计链路分布情况

        Args:
            domains: 测试域名列表（默认包含国内外典型域名）
            max_hops: traceroute 最大跳数（默认15，提高检测效率）
            cpe_exit_hop: CPE出口跳数（默认第2跳是CPE，从第3跳开始分析）
            ctx: 流程上下文（可选）

        Returns:
            CpeLinkRouteResult: CPE链路分流测试结果
        """
        import time
        
        # 默认测试域名集合（覆盖国内外典型业务）
        if domains is None:
            domains = [
                "www.baidu.com",      # 国内搜索
                "www.google.com",     # 国际搜索
                "www.youtube.com",    # 国际视频
                "www.tiktok.com",     # 国际短视频
            ]

        start_time = time.monotonic()
        result = CpeLinkRouteResult(total_domains_tested=len(domains))

        if not ctx:
            # 创建临时上下文
            import uuid
            ctx = FlowContext(trace_id=str(uuid.uuid4()))

        logger.info(
            f"开始CPE链路分流检测: {len(domains)}个目标域名",
            extra={"trace_id": ctx.trace_id},
        )

        try:
            # 步骤1: 对每个域名执行 DNS 解析 + Traceroute
            domain_results = []
            for domain in domains:
                try:
                    path_result = await self._analyze_domain_path(
                        domain=domain,
                        max_hops=max_hops,
                        cpe_exit_hop=cpe_exit_hop,
                        ctx=ctx
                    )
                    domain_results.append(path_result)
                    logger.debug(
                        f"域名 {domain} 路径分析完成: fingerprint={path_result.path_fingerprint}",
                        extra={"trace_id": ctx.trace_id}
                    )
                except Exception as e:
                    logger.warning(
                        f"域名 {domain} 路径分析失败: {e}",
                        extra={"trace_id": ctx.trace_id}
                    )
                    result.errors.append(f"域名 {domain} 分析失败: {str(e)}")

            result.domain_results = domain_results

            # 步骤2: 基于路径指纹进行链路分组
            link_groups = self._group_by_path_fingerprint(domain_results)
            result.link_distribution = link_groups
            result.detected_links = list(link_groups.keys())
            result.multi_link_count = len(link_groups)
            result.is_multi_link = len(link_groups) > 1

            # 步骤3: 生成检测报告摘要
            if result.is_multi_link:
                logger.info(
                    f"CPE链路分流检测完成: 检测到 {result.multi_link_count} 条不同链路",
                    extra={"trace_id": ctx.trace_id}
                )
                for link_fp, domains_in_link in link_groups.items():
                    logger.info(
                        f"  - 链路 [{link_fp}]: {', '.join(domains_in_link)}",
                        extra={"trace_id": ctx.trace_id}
                    )
            else:
                logger.info(
                    "CPE链路分流检测完成: 所有域名使用相同链路",
                    extra={"trace_id": ctx.trace_id}
                )

        except Exception as e:
            logger.error(
                f"CPE链路分流检测异常: {e}",
                extra={"trace_id": ctx.trace_id},
                exc_info=True
            )
            result.errors.append(f"检测过程异常: {str(e)}")

        finally:
            result.total_duration_ms = (time.monotonic() - start_time) * 1000

        return result

    async def _analyze_domain_path(
        self,
        domain: str,
        max_hops: int = 6,  # 优化：只追踪前6跳，大幅缩短执行时间
        cpe_exit_hop: int = 2,
        ctx: FlowContext = None,
    ) -> DomainPathAnalysisResult:
        """分析单个域名的完整路径

        Args:
            domain: 目标域名
            max_hops: traceroute 最大跳数（优化为6跳，足够识别CPE后的链路）
            cpe_exit_hop: CPE出口跳数
            ctx: 流程上下文

        Returns:
            DomainPathAnalysisResult: 域名路径分析结果
        """
        from sdwan_desktop.tools.registry.base import ToolDispatcher
        from sdwan_desktop.core.types.tool import ToolRequest
        
        dispatcher = ToolDispatcher()
        path_result = DomainPathAnalysisResult(domain=domain, cpe_exit_hop=cpe_exit_hop)

        # 步骤1: DNS解析获取目标IP
        try:
            request = ToolRequest(
                tool_name="dns",
                parameters={
                    "domain": domain,
                    "record_type": "A",
                    "timeout": 5
                },
                timeout_seconds=10,
                trace_id=ctx.trace_id if ctx else None
            )
            
            response = await dispatcher.dispatch(
                tool_name="dns",
                request=request,
                ctx=ctx
            )
            
            if response.success and response.data:
                resolved_ips = response.data.get("resolved_ips", [])
                if resolved_ips:
                    path_result.resolved_ip = resolved_ips[0]
                else:
                    path_result.resolved_ip = "DNS解析失败"
                    logger.warning(f"域名 {domain} DNS解析结果为空", extra={"trace_id": ctx.trace_id})
            else:
                path_result.resolved_ip = f"DNS查询失败: {response.error_message}"
                logger.warning(f"域名 {domain} DNS查询失败: {response.error_message}", extra={"trace_id": ctx.trace_id})
        except Exception as e:
            path_result.resolved_ip = f"DNS异常: {str(e)}"
            logger.warning(f"域名 {domain} DNS解析异常: {e}", extra={"trace_id": ctx.trace_id})

        # 步骤2: 执行 Traceroute（仅前6跳）
        try:
            request = ToolRequest(
                tool_name="traceroute",
                parameters={
                    "host": domain,
                    "max_hops": max_hops,  # 优化：仅追踪6跳
                    "timeout": 2  # 每跳超时2秒，配合 -d 参数禁用DNS解析，加快执行速度
                },
                timeout_seconds=30,  # 优化：6跳 * 2秒 + 缓冲 = 约15秒，设置30秒足够
                trace_id=ctx.trace_id if ctx else None
            )
            
            response = await dispatcher.dispatch(
                tool_name="traceroute",
                request=request,
                ctx=ctx
            )
            
            if response.success and response.data:
                hops_data = response.data.get("hops", [])
                
                # 解析 traceroute 结果
                for hop_data in hops_data:
                    # 兼容处理：traceroute 工具返回 'ip' 字段（字符串），转换为 'ip_addresses'（列表）
                    ip_value = hop_data.get('ip', '')
                    ip_list = [ip_value] if ip_value and ip_value != '*' else []
                    
                    hop_info = TracerouteHopInfo(
                        hop_number=hop_data.get('hop', 0),
                        ip_addresses=hop_data.get('ip_addresses', ip_list),  # 优先使用 ip_addresses，否则使用转换后的 ip
                        rtts=hop_data.get('rtts', []),
                        is_timeout=hop_data.get('is_timeout', False) or (ip_value == '*')
                    )
                    path_result.full_path.append(hop_info)
                
                # 提取 CPE 之后的路径（从第3跳开始）
                post_cpe_hops = [
                    hop for hop in path_result.full_path 
                    if hop.hop_number > cpe_exit_hop
                ]
                path_result.post_cpe_hops = post_cpe_hops
                
                # 生成路径指纹（扩展版：取前6跳，兼容超时和缺失IP）
                fingerprint_parts = []
                max_fingerprint_hops = 6  # 扩展到6跳以充分反映路径差异
                
                for hop in post_cpe_hops[:max_fingerprint_hops]:
                    if hop.ip_addresses:
                        # 有有效IP，使用第一个IP
                        ip_str = hop.ip_addresses[0]
                    elif hop.is_timeout:
                        # 超时跳点，标记为 T (Timeout)
                        ip_str = "T"
                    else:
                        # 其他异常情况，标记为 ?
                        ip_str = "?"
                    
                    # 格式：跳号:IP，例如 "3:8.1.3.1" 或 "4:T"
                    fingerprint_parts.append(f"{hop.hop_number}:{ip_str}")
                
                # 优化：只要有部分跳点就生成指纹
                if fingerprint_parts:
                    path_result.path_fingerprint = "->".join(fingerprint_parts)
                else:
                    path_result.path_fingerprint = "无有效跳点"
                
                # 初步判断链路类型（基于IP段特征）
                # 过滤掉超时和异常跳点后分类
                valid_ips = [h.ip_addresses[0] for h in post_cpe_hops[:max_fingerprint_hops] if h.ip_addresses]
                path_result.link_category = self._classify_link_type(valid_ips)
                
                # 计算置信度（基于路径完整性）
                total_hops = min(max_fingerprint_hops, len(post_cpe_hops))
                if total_hops > 0:
                    valid_hop_count = len([h for h in post_cpe_hops[:max_fingerprint_hops] if h.ip_addresses])
                    timeout_hop_count = len([h for h in post_cpe_hops[:max_fingerprint_hops] if h.is_timeout])
                    
                    # 综合评估：有效跳点比例 + 超时跳点惩罚
                    completeness = valid_hop_count / total_hops
                    
                    if completeness >= 0.8:  # 80%以上有效跳点
                        path_result.confidence = 0.95
                    elif completeness >= 0.6:  # 60-80%有效跳点
                        path_result.confidence = 0.85
                    elif completeness >= 0.4:  # 40-60%有效跳点
                        # 如果超时跳点过多，降低置信度
                        if timeout_hop_count > total_hops * 0.3:
                            path_result.confidence = 0.6
                        else:
                            path_result.confidence = 0.7
                    else:  # 低于40%有效跳点
                        path_result.confidence = 0.4
                else:
                    path_result.confidence = 0.2

        except Exception as e:
            logger.error(f"域名 {domain} traceroute 失败: {e}", extra={"trace_id": ctx.trace_id})
            path_result.path_fingerprint = f"traceroute异常: {str(e)[:50]}"
            path_result.confidence = 0.0

        return path_result
