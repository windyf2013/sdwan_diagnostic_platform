"""
智能路径分析器 - 动态识别 CPE 出口和分流点

替代固定的"第2跳是CPE"假设，通过分析 Traceroute 跳点的 IP 特征、RTT 突变等
智能判断网络拓扑结构。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


# ==================== 缓存数据结构定义 ====================

@dataclass(slots=True)
class DnsResolutionEntry:
    """DNS解析缓存条目
    
    用于在 Flow 步骤之间共享 DNS 解析结果，避免重复查询。
    
    Attributes:
        domain: 域名
        domestic_ips: 国内DNS解析得到的IP列表
        international_ips: 国际DNS解析得到的IP列表
        is_split: 是否存在分流差异
        query_time_ms: DNS查询耗时（毫秒）
    """
    domain: str
    domestic_ips: List[str] = field(default_factory=list)
    international_ips: List[str] = field(default_factory=list)
    is_split: bool = False
    query_time_ms: float = 0.0
    
    def to_dict(self) -> dict:
        """转换为字典（用于序列化到 Context）"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DnsResolutionEntry':
        """从字典恢复（用于从 Context 读取）"""
        return cls(**data)
    
    def validate(self) -> bool:
        """验证数据完整性"""
        return bool(
            self.domain and 
            (self.domestic_ips or self.international_ips)
        )
    
    def get_all_ips(self) -> List[str]:
        """获取所有解析到的IP（去重）"""
        return list(set(self.domestic_ips + self.international_ips))


@dataclass(slots=True)
class TcpingResultEntry:
    """TCPing结果缓存条目
    
    用于在 Flow 步骤之间共享 TCP 端口探测结果。
    
    Attributes:
        target: 目标地址（IP:Port 或 域名:Port）
        is_reachable: 是否可达
        avg_response_time_ms: 平均响应时间（毫秒）
        packet_loss_rate: 丢包率（0-1）
        probe_time_ms: 探测耗时（毫秒）
    """
    target: str
    is_reachable: bool = False
    avg_response_time_ms: float = 0.0
    packet_loss_rate: float = 0.0
    probe_time_ms: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TcpingResultEntry':
        return cls(**data)


@dataclass(slots=True)
class TracerouteResultEntry:
    """Traceroute结果缓存条目
    
    用于在 Flow 步骤之间共享路由追踪结果。
    
    Attributes:
        domain: 域名
        resolved_ip: 解析后的IP地址
        ip_version: IP版本（IPv4/IPv6）
        full_path: 完整路径跳点列表（字典格式）
        path_fingerprint: 路径指纹字符串
        link_category: 链路分类（domestic/international/unknown）
        confidence: 分析置信度（0-1）
        duration_ms: 总耗时（毫秒）
    """
    domain: str
    resolved_ip: str = ""
    ip_version: str = "unknown"
    full_path: List[dict] = field(default_factory=list)
    path_fingerprint: str = ""
    link_category: str = "unknown"
    confidence: float = 0.0
    duration_ms: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TracerouteResultEntry':
        return cls(**data)
    
    def get_hop_count(self) -> int:
        """获取跳点数"""
        return len(self.full_path)
    
    def has_valid_path(self) -> bool:
        """验证是否有有效路径"""
        return bool(self.resolved_ip and self.full_path)


# ==================== 原有数据结构 ====================

@dataclass
class PathAnalysisResult:
    """智能路径分析结果"""
    
    cpe_hop: int = 2
    """识别出的 CPE/网关跳数"""
    
    split_point_hop: int = 3
    """识别出的分流起始跳数（CPE之后）"""
    
    deployment_mode: str = "unknown"
    """推测的部署模式: direct/pppoe/bridge/router"""
    
    path_fingerprint: str = ""
    """基于智能分析生成的路径指纹"""
    
    confidence: float = 0.5
    """分析置信度 (0-1)"""
    
    reasoning: List[str] = field(default_factory=list)
    """推理过程记录"""


class SmartPathAnalyzer:
    """智能路径分析器"""

    def analyze(self, hops: List["TracerouteHopInfo"]) -> PathAnalysisResult:
        """分析路径跳点，识别关键节点
        
        Args:
            hops: Traceroute 跳点列表
            
        Returns:
            PathAnalysisResult: 分析结果
        """
        result = PathAnalysisResult()
        
        if not hops:
            result.reasoning.append("无跳点数据")
            return result

        # 1. 识别局域网段 (RFC1918)
        private_hops = []
        public_start_index = -1
        
        for i, hop in enumerate(hops):
            if not hop.ip_addresses:
                continue
            
            ip = hop.ip_addresses[0]
            if self._is_private_ip(ip):
                private_hops.append(i)
            else:
                if public_start_index == -1:
                    public_start_index = i
                    result.reasoning.append(f"在第 {hop.hop_number} 跳 ({ip}) 发现首个公网IP")

        # 2. 确定 CPE 位置
        # 通常最后一个私有IP跳点是 CPE 或最后一跳网关
        if private_hops:
            # 假设最后一个私有跳点是 CPE 出口
            last_private_idx = private_hops[-1]
            result.cpe_hop = hops[last_private_idx].hop_number
            result.reasoning.append(f"识别最后一个私有IP跳点 {hops[last_private_idx].hop_number} 为 CPE/网关边界")
            
            # 分流点通常是 CPE 之后的第一跳
            if last_private_idx + 1 < len(hops):
                result.split_point_hop = hops[last_private_idx + 1].hop_number
            else:
                result.split_point_hop = result.cpe_hop + 1
        else:
            # 如果没有私有IP（罕见，可能是直连公网或测试环境），默认第1跳后开始
            result.cpe_hop = 1
            result.split_point_hop = 2
            result.reasoning.append("未发现私有IP，假设直连或特殊拓扑")

        # 3. 生成指纹 (从分流点开始)
        fingerprint_parts = []
        max_hops = 6
        count = 0
        for hop in hops:
            if hop.hop_number >= result.split_point_hop:
                ip_str = hop.ip_addresses[0] if hop.ip_addresses else ("T" if hop.is_timeout else "?")
                fingerprint_parts.append(f"{hop.hop_number}:{ip_str}")
                count += 1
                if count >= max_hops:
                    break
        
        result.path_fingerprint = "->".join(fingerprint_parts) if fingerprint_parts else "无有效路径"
        
        # 4. 简单置信度计算
        if result.path_fingerprint and result.path_fingerprint != "无有效路径":
            result.confidence = 0.85
        else:
            result.confidence = 0.4

        return result

    @staticmethod
    def _is_private_ip(ip: str) -> bool:
        """检查是否为私有IP"""
        if not ip or ip in ["*", "T", "?"]:
            return False
        try:
            import ipaddress
            addr = ipaddress.ip_address(ip)
            return addr.is_private
        except ValueError:
            return False
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
    
    hostnames: List[str] = field(default_factory=list)
    """该跳的主机名列表（反向DNS解析结果，可能为空）"""
    
    rtts: List[float] = field(default_factory=list)
    """往返时间列表（毫秒）"""
    
    is_timeout: bool = False
    """是否超时"""
    
    # ✅ 新增字段：支持智能路径分析
    as_number: Optional[str] = None
    """AS号（自治系统号）"""
    
    country: Optional[str] = None
    """国家/地区代码"""
    
    isp: Optional[str] = None
    """运营商名称"""
    
    latency_class: Optional[str] = None
    """延迟等级：lan/wan/internet（基于RTT自动分类）"""


@dataclass(slots=True)
class DomainPathAnalysisResult:
    """单个域名的路径分析结果"""

    domain: str = ""
    """目标域名"""
    
    resolved_ip: str = "N/A"
    """解析后的IP地址"""
    
    ip_version: str = "unknown"
    """IP协议版本: IPv4/IPv6/unknown（确保DNS解析和Traceroute使用相同协议栈）"""
    
    full_path: List["TracerouteHopInfo"] = field(default_factory=list)
    """完整路径（所有跳）"""
    
    cpe_exit_hop: int = 2
    """CPE出口跳数（智能分析结果，默认为2）"""
    
    split_point_hop: int = 3
    """分流起始跳数（智能分析结果，默认为3）"""
    
    deployment_mode: str = "unknown"
    """推测的部署模式 (智能分析结果)"""
    
    post_cpe_hops: List["TracerouteHopInfo"] = field(default_factory=list)
    """CPE之后的路径（用于分析分流）"""
    
    path_fingerprint: str = ""
    """路径指纹（用于快速比对，如 "8.1.3.1->5.1.1.2"）"""
    
    link_category: str = "unknown"
    """链路分类: domestic/international/unknown"""
    
    confidence: float = 0.0
    """路径识别置信度 (0-1)"""
    
    reasoning: List[str] = field(default_factory=list)
    """智能分析的推理过程记录"""
    
    # ✅ 新增：路径质量指标
    avg_rtt_ms: float = 0.0
    """平均往返时延（毫秒）"""
    
    max_rtt_ms: float = 0.0
    """最大往返时延（毫秒）"""
    
    timeout_hop_count: int = 0
    """超时跳点数量"""
    
    total_hop_count: int = 0
    """总跳点数"""
    
    path_quality_score: float = 0.0
    """路径质量评分 (0-100)，综合RTT、丢包、超时等因素"""


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
        max_concurrent: int = 8,  # ✅ 优化：从5增加到8，提升DNS查询效率，应对部分DNS不可达场景
    ):
        """初始化DNS分流测试器

        Args:
            dispatcher: 工具调度器，如果为None则创建新实例
            max_concurrent: 最大并发DNS查询数（默认8，平衡速度与稳定性）
        """
        # ✅ 关键修复：确保dns模块已导入，触发装饰器注册DNS工具
        from sdwan_desktop.tools.implementations.network.dns import DnsTool  # noqa: F401
        
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

    async def test_optimized(
        self,
        domains: List[str] = None,
        domestic_dns: List[str] = None,
        international_dns: List[str] = None,
        ctx: Optional[FlowContext] = None,
        use_cache: bool = True,
    ) -> DnsSplitTestResult:
        """优化的DNS分流测试（支持结果缓存和复用）

        优化策略：
        1. 使用统一的域名目标集
        2. ✅ 真正使用缓存：检查 Context 中的 DNS 解析缓存，避免重复查询
        3. 将 DNS 解析结果存入 Context，供后续步骤复用

        Args:
            domains: 测试域名列表（默认使用统一域名集）
            domestic_dns: 国内DNS服务器列表
            international_dns: 国际DNS服务器列表
            ctx: 流程上下文
            use_cache: 是否使用缓存（默认True）

        Returns:
            DnsSplitTestResult: DNS分流测试结果
        """
        from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS
        
        # ✅ 使用统一域名集
        if domains is None:
            domains = DEFAULT_TEST_DOMAINS
        
        if not ctx:
            import uuid
            ctx = FlowContext(trace_id=str(uuid.uuid4()))
        
        # ✅ 关键修复：真正使用DNS缓存，避免重复查询
        dns_cache_dict = ctx.get("dns_resolution_cache") if use_cache else None
        
        # 分离已缓存和未缓存的域名
        cached_domains = []
        uncached_domains = []
        
        if dns_cache_dict:
            for domain in domains:
                if domain in dns_cache_dict:
                    cached_domains.append(domain)
                else:
                    uncached_domains.append(domain)
            
            logger.info(
                f"DNS缓存命中情况: {len(cached_domains)}/{len(domains)}个域名已缓存",
                extra={"trace_id": ctx.trace_id}
            )
            
            if cached_domains:
                logger.info(
                    f"✅ 跳过已缓存域名的DNS查询: {', '.join(cached_domains[:3])}{'...' if len(cached_domains) > 3 else ''}",
                    extra={"trace_id": ctx.trace_id}
                )
        else:
            uncached_domains = domains
            logger.info(
                "无DNS缓存，将执行完整查询",
                extra={"trace_id": ctx.trace_id}
            )
        
        # ✅ 初始化结果对象
        result = DnsSplitTestResult(total_domains=len(domains))
        
        # ✅ 步骤1：从缓存恢复已缓存域名的结果
        if cached_domains and dns_cache_dict:
            for domain in cached_domains:
                cache_entry_dict = dns_cache_dict[domain]
                # 从字典重建 DomainDnsResult
                domain_result = DomainDnsResult(domain=domain)
                domain_result.is_split = cache_entry_dict.get("is_split", False)
                domain_result.split_description = "从缓存恢复"
                domain_result.domestic_avg_rtt_ms = cache_entry_dict.get("query_time_ms", 0)
                
                # 恢复IP列表（简化版，实际应该存储完整的domestic_results和international_results）
                domestic_ips = cache_entry_dict.get("domestic_ips", [])
                international_ips = cache_entry_dict.get("international_ips", [])
                
                # 模拟domestic_results和international_results结构
                if domestic_ips:
                    domain_result.domestic_results["cached"] = domestic_ips
                if international_ips:
                    domain_result.international_results["cached"] = international_ips
                
                result.domain_results.append(domain_result)
                if domain_result.is_split:
                    result.split_domains.append(domain)
                    result.split_count += 1
            
            logger.info(
                f"✅ 已从缓存恢复 {len(cached_domains)} 个域名的DNS结果",
                extra={"trace_id": ctx.trace_id}
            )
        
        # ✅ 步骤2：仅对未缓存的域名执行真实查询
        if uncached_domains:
            logger.info(
                f"开始查询 {len(uncached_domains)} 个未缓存域名: {', '.join(uncached_domains[:3])}{'...' if len(uncached_domains) > 3 else ''}",
                extra={"trace_id": ctx.trace_id}
            )
            
            try:
                import asyncio
                
                # ✅ 内部超时保护：70秒（比Flow层80秒略短）
                uncached_result = await asyncio.wait_for(
                    self.test_all_domains(
                        domains=uncached_domains,
                        domestic_dns=domestic_dns or ["218.201.96.130", "211.137.191.26"],
                        international_dns=international_dns or ["8.8.8.8", "1.1.1.1"],
                        ctx=ctx
                    ),
                    timeout=70  # ✅ 精简DNS后调整为70秒
                )
                
                # 合并未缓存域名的结果
                result.domain_results.extend(uncached_result.domain_results)
                result.split_domains.extend(uncached_result.split_domains)
                result.split_count += uncached_result.split_count
                result.errors.extend(uncached_result.errors)
                
                logger.info(
                    f"✅ 完成 {len(uncached_domains)} 个域名的DNS查询",
                    extra={"trace_id": ctx.trace_id}
                )
                
            except asyncio.TimeoutError:
                logger.error(
                    f"DNS分流测试超时（70秒），已完成部分测试",
                    extra={"trace_id": ctx.trace_id}
                )
                # ✅ 创建错误结果并保存到Context，确保数据链路完整
                error_result = DnsSplitTestResult(
                    total_domains=len(uncached_domains),
                    errors=[f"DNS分流测试超时（70秒），可能原因：DNS服务器响应慢或网络延迟高"]
                )
                # 为未完成的域名创建空结果
                for domain in uncached_domains:
                    empty_result = DomainDnsResult(domain=domain)
                    empty_result.is_split = False
                    empty_result.split_description = "测试超时，未完成"
                    error_result.domain_results.append(empty_result)
                
                # 合并错误结果
                result.domain_results.extend(error_result.domain_results)
                result.errors.extend(error_result.errors)
        else:
            logger.info(
                "✅ 所有域名均已缓存，跳过DNS查询，立即返回",
                extra={"trace_id": ctx.trace_id}
            )
        
        # ✅ 步骤3：更新缓存（将新查询的结果也加入缓存）
        dns_cache_entries: Dict[str, DnsResolutionEntry] = {}
        
        # 先加载已有缓存
        if dns_cache_dict:
            for domain, entry_dict in dns_cache_dict.items():
                dns_cache_entries[domain] = DnsResolutionEntry.from_dict(entry_dict)
        
        # 再添加/更新新查询的结果
        for domain_result in result.domain_results:
            # ✅ 修复：domestic_results 和 international_results 是字典 {dns_server: ip_list}
            # 需要提取所有DNS服务器的解析结果并合并
            domestic_ips = []
            international_ips = []
            
            for dns_server, ips in domain_result.domestic_results.items():
                if isinstance(ips, list):
                    # 过滤掉错误信息
                    domestic_ips.extend([ip for ip in ips if not ip.startswith("ERROR:")])
            
            for dns_server, ips in domain_result.international_results.items():
                if isinstance(ips, list):
                    # 过滤掉错误信息
                    international_ips.extend([ip for ip in ips if not ip.startswith("ERROR:")])
            
            entry = DnsResolutionEntry(
                domain=domain_result.domain,
                domestic_ips=domestic_ips,
                international_ips=international_ips,
                is_split=domain_result.is_split,
                query_time_ms=domain_result.domestic_avg_rtt_ms  # 使用国内DNS平均RTT作为参考
            )
            dns_cache_entries[domain_result.domain] = entry
        
        # 存入 Context 时转换为字典（保持兼容性）
        ctx.set("dns_resolution_cache", {
            k: v.to_dict() for k, v in dns_cache_entries.items()
        })
        
        # ✅ 关键修复：将整个测试结果也存入 Context，供报告生成器使用
        ctx.set("dns_split_result", result)
        
        logger.info(
            f"DNS解析结果已缓存到Context（{len(dns_cache_entries)}个域名），可供后续步骤复用",
            extra={"trace_id": ctx.trace_id}
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

    @staticmethod
    def _calculate_optimal_max_hops(domain: str) -> tuple:
        """根据目标域名智能计算最优跳数和超时配置
        
        ✅ 优化策略：统一限制为前 7 跳，平衡探测深度与测试效率。
        对于 SD-WAN CPE 分流检测，前 7 跳通常已足够识别：
        - 第 1-2 跳：客户端 → 网关/CPE
        - 第 3-4 跳：CPE WAN 出口 → ISP 接入点
        - 第 5-7 跳：ISP 核心网 → 互联网骨干
        
        Args:
            domain: 目标域名
            
        Returns:
            (max_hops, timeout_per_hop, total_timeout) 三元组
        """
        domain_lower = domain.lower()
        
        # ✅ 统一配置：所有场景均使用 7 跳
        # 理由：
        # 1. CPE 分流检测主要关注前几跳的路径差异
        # 2. 7 跳足以覆盖从客户端到 ISP 核心的路径
        # 3. 大幅缩短测试时间（从 90-120 秒降至约 105 秒）
        # 4. 减少中间节点超时导致的误判
        
        max_hops = 7
        timeout_per_hop = 5  # 每跳 5 秒超时（考虑网络波动）
        total_timeout = 105  # 总超时 105 秒（5秒 × 7跳 × 3次重试安全系数）
        
        return (max_hops, timeout_per_hop, total_timeout)
    
    async def _analyze_domain_path(
        self,
        domain: str,
        max_hops: int = None,
        cpe_exit_hop: int = 2,
        ctx: Optional[FlowContext] = None,
    ) -> DomainPathAnalysisResult:
        """分析单个域名的网络路径
        
        执行完整的探测流程：DNS解析 → TCPing可达性测试 → Traceroute路径追踪
        
        Args:
            domain: 目标域名
            max_hops: Traceroute最大跳数（None则智能计算）
            cpe_exit_hop: CPE出口跳数
            ctx: 流程上下文
            
        Returns:
            DomainPathAnalysisResult: 域名路径分析结果
        """
        import time
        
        path_result = DomainPathAnalysisResult(domain=domain)
        
        if not ctx:
            import uuid
            ctx = FlowContext(trace_id=str(uuid.uuid4()))
        
        start_time = time.monotonic()
        
        try:
            # ✅ 步骤1: DNS解析获取目标IP（优先使用缓存）
            dns_cache_dict = ctx.get("dns_resolution_cache")
            
            if dns_cache_dict and domain in dns_cache_dict:
                # 使用缓存的DNS解析结果
                cached_dns = dns_cache_dict[domain]
                resolved_ips = cached_dns.get("resolved_ips", [])
                
                if not resolved_ips:
                    path_result.path_fingerprint = "DNS缓存中无有效IP"
                    path_result.link_category = "no_ip"
                    path_result.confidence = 0.0
                    return path_result
                
                path_result.resolved_ip = resolved_ips[0]
                path_result.ip_version = self._detect_ip_version(path_result.resolved_ip)
                
                logger.info(
                    f"✅ 复用DNS缓存: {domain} -> {path_result.resolved_ip}",
                    extra={"trace_id": ctx.trace_id}
                )
            else:
                # 执行DNS解析
                dns_request = ToolRequest(
                    tool_name="dns",
                    parameters={"domain": domain},
                    timeout_seconds=10,
                    trace_id=ctx.trace_id
                )
                
                dns_response = await self.dispatcher.dispatch(
                    tool_name="dns",
                    request=dns_request,
                    ctx=ctx
                )
                
                if not dns_response.success or not dns_response.data:
                    path_result.path_fingerprint = f"DNS解析失败: {dns_response.error_message[:50]}"
                    path_result.link_category = "error"
                    path_result.confidence = 0.0
                    return path_result
                
                resolved_ips = dns_response.data.get("resolved_ips", [])
                if not resolved_ips:
                    path_result.path_fingerprint = "DNS解析返回空IP列表"
                    path_result.link_category = "no_ip"
                    path_result.confidence = 0.0
                    return path_result
                
                path_result.resolved_ip = resolved_ips[0]
                path_result.ip_version = self._detect_ip_version(path_result.resolved_ip)
                
                logger.debug(
                    f"域名 {domain} DNS解析成功: {path_result.resolved_ip} ({path_result.ip_version})",
                    extra={"trace_id": ctx.trace_id}
                )
            
            # ✅ 步骤2: TCPing快速判断可达性（优先使用缓存）
            tcping_cache_dict = ctx.get("tcping_results_cache")
            is_reachable = False
            
            if tcping_cache_dict and domain in tcping_cache_dict:
                # 使用缓存的TCPing结果
                cached_tcping = tcping_cache_dict[domain]
                is_reachable = cached_tcping.get("success", False)
                rtt_avg = cached_tcping.get("rtt_avg")
                loss_rate = cached_tcping.get("loss_rate")
                
                logger.info(
                    f"✅ 复用TCPing缓存: {domain}, 可达={is_reachable}, RTT={rtt_avg}ms, 丢包率={loss_rate}",
                    extra={"trace_id": ctx.trace_id}
                )
            else:
                # 执行TCPing测试
                # ✅ 优化：降低超时时间，让不可达目标快速失败（适配CPE测试60秒总超时）
                # 优先测试 HTTPS (443)
                tcping_request_443 = ToolRequest(
                    tool_name="tcping",
                    parameters={
                        "host": path_result.resolved_ip,
                        "port": 443,
                        "count": 1,  # ✅ 减少探测次数：从2次降至1次
                        "timeout": 2  # ✅ 降低单次超时：从3秒降至2秒
                    },
                    timeout_seconds=5,  # ✅ 降低总超时：从8秒降至5秒
                    trace_id=ctx.trace_id
                )
                
                tcping_response_443 = await self.dispatcher.dispatch(
                    tool_name="tcping",
                    request=tcping_request_443,
                    ctx=ctx
                )
                
                if tcping_response_443.success and tcping_response_443.data:
                    loss_rate_443 = tcping_response_443.data.get("loss_rate", 1.0)
                    port_open_443 = tcping_response_443.data.get("port_open", False)
                    is_reachable = loss_rate_443 < 0.5 and port_open_443
                    
                    logger.debug(
                        f"域名 {domain} TCPing测试结果: 端口443, 开放={port_open_443}, 丢包率={loss_rate_443:.1%}, 可达={is_reachable}",
                        extra={"trace_id": ctx.trace_id}
                    )
                
                # 如果443端口不通，尝试80端口
                if not is_reachable:
                    tcping_request_80 = ToolRequest(
                        tool_name="tcping",
                        parameters={
                            "host": path_result.resolved_ip,
                            "port": 80,
                            "count": 1,  # ✅ 减少探测次数：从2次降至1次
                            "timeout": 2  # ✅ 降低单次超时：从3秒降至2秒
                        },
                        timeout_seconds=5,  # ✅ 降低总超时：从8秒降至5秒
                        trace_id=ctx.trace_id
                    )
                    
                    tcping_response_80 = await self.dispatcher.dispatch(
                        tool_name="tcping",
                        request=tcping_request_80,
                        ctx=ctx
                    )
                    
                    if tcping_response_80.success and tcping_response_80.data:
                        loss_rate_80 = tcping_response_80.data.get("loss_rate", 1.0)
                        port_open_80 = tcping_response_80.data.get("port_open", False)
                        is_reachable = loss_rate_80 < 0.5 and port_open_80
                        
                        logger.debug(
                            f"域名 {domain} TCPing测试结果: 端口80, 开放={port_open_80}, 丢包率={loss_rate_80:.1%}, 可达={is_reachable}",
                            extra={"trace_id": ctx.trace_id}
                        )
            
            # 关键决策点：根据Ping结果决定是否执行Traceroute
            if not is_reachable:
                logger.info(
                    f"域名 {domain} TCPing测试显示不可达，跳过Traceroute以节省时间",
                    extra={"trace_id": ctx.trace_id}
                )
                path_result.path_fingerprint = "TCPing测试不可达-跳过Traceroute"
                path_result.link_category = "unreachable"
                path_result.confidence = 0.9
                return path_result
            
            # 步骤3: TCPing可达，执行Traceroute分析路径
            if max_hops is None:
                max_hops, timeout_per_hop, total_timeout = self._calculate_optimal_max_hops(domain)
            else:
                _, timeout_per_hop, total_timeout = self._calculate_optimal_max_hops(domain)
            
            logger.debug(
                f"Traceroute配置: domain={domain}, max_hops={max_hops}, "
                f"timeout_per_hop={timeout_per_hop}s, total_timeout={total_timeout}s",
                extra={"trace_id": ctx.trace_id}
            )
            
            traceroute_request = ToolRequest(
                tool_name="traceroute",
                parameters={
                    "host": path_result.resolved_ip,
                    "max_hops": max_hops,
                    "timeout": timeout_per_hop
                },
                timeout_seconds=total_timeout,
                trace_id=ctx.trace_id
            )
            
            traceroute_response = await self.dispatcher.dispatch(
                tool_name="traceroute",
                request=traceroute_request,
                ctx=ctx
            )
            
            if not traceroute_response.success:
                logger.warning(
                    f"域名 {domain} Traceroute执行失败: {traceroute_response.error_message}",
                    extra={"trace_id": ctx.trace_id}
                )
                path_result.path_fingerprint = f"Traceroute执行失败: {traceroute_response.error_message[:50]}"
                path_result.link_category = "traceroute_failed"
                path_result.confidence = 0.3
                return path_result
            
            if not traceroute_response.data:
                path_result.path_fingerprint = "Traceroute返回数据为空"
                path_result.link_category = "no_data"
                path_result.confidence = 0.3
                return path_result
            
            hops_data = traceroute_response.data.get("hops", [])
            
            if not hops_data:
                path_result.path_fingerprint = "Traceroute未获取到任何跳点"
                path_result.link_category = "no_hops"
                path_result.confidence = 0.3
                return path_result
            
            # 解析 traceroute 结果
            for hop_data in hops_data:
                ip_value = hop_data.get('ip', '')
                ip_list = [ip_value] if ip_value and ip_value != '*' else []
                
                hostname_value = hop_data.get('hostname', '')
                hostname_list = [hostname_value] if hostname_value and hostname_value != '*' else []
                
                hop_info = TracerouteHopInfo(
                    hop_number=hop_data.get('hop', 0),
                    ip_addresses=hop_data.get('ip_addresses', ip_list),
                    hostnames=hostname_list,
                    rtts=hop_data.get('rtts', []),
                    is_timeout=hop_data.get('is_timeout', False) or (ip_value == '*')
                )
                path_result.full_path.append(hop_info)
            
            # ✅ 新增：批量查询ASN信息（避免重复查询）
            try:
                from .ip_geo_service import IPGeoService
                
                # 收集所有需要查询的IP地址
                ips_to_query = set()
                for hop in path_result.full_path:
                    if not hop.is_timeout and hop.ip_addresses:
                        for ip in hop.ip_addresses:
                            if ip and ip != '*':
                                ips_to_query.add(ip)
                
                # 批量查询ASN信息
                if ips_to_query:
                    geo_service = IPGeoService()
                    ip_geo_cache = {}
                    
                    for ip in ips_to_query:
                        geo_info = geo_service.query_ip(ip)
                        if geo_info:
                            ip_geo_cache[ip] = geo_info
                    
                    # 填充到每个跳点
                    for hop in path_result.full_path:
                        if not hop.is_timeout and hop.ip_addresses:
                            # 使用第一个IP的地理信息
                            first_ip = hop.ip_addresses[0]
                            if first_ip in ip_geo_cache:
                                geo_info = ip_geo_cache[first_ip]
                                hop.as_number = geo_info.get('as_number')
                                hop.country = geo_info.get('country')
                                hop.isp = geo_info.get('isp')
                                
                                logger.debug(
                                    f"IP {first_ip} ASN信息: AS{hop.as_number}, "
                                    f"{hop.country}, {hop.isp}"
                                )
                    
                    logger.info(
                        f"✅ ASN查询完成: {len(ip_geo_cache)}/{len(ips_to_query)} 个IP"
                    )
            
            except Exception as e:
                logger.warning(f"ASN查询失败，路径将不包含ASN信息: {e}")
                # 不中断流程，继续执行
            
            # 使用智能路径分析器
            try:
                from .smart_path_analyzer import SmartPathAnalyzer
                
                analyzer = SmartPathAnalyzer()
                analysis_result = analyzer.analyze(path_result.full_path)
                
                path_result.cpe_exit_hop = analysis_result.cpe_hop
                path_result.split_point_hop = analysis_result.split_point_hop
                path_result.deployment_mode = analysis_result.deployment_mode
                path_result.path_fingerprint = analysis_result.path_fingerprint
                path_result.confidence = analysis_result.confidence
                path_result.reasoning = analysis_result.reasoning
                
                logger.info(
                    f"✅ 智能路径分析: 域名={domain}, "
                    f"CPE在第{analysis_result.cpe_hop}跳, "
                    f"分流点在第{analysis_result.split_point_hop}跳, "
                    f"部署模式={analysis_result.deployment_mode}, "
                    f"置信度={analysis_result.confidence:.2f}"
                )
                
            except Exception as e:
                logger.warning(
                    f"智能路径分析失败，使用降级策略: {e}",
                    extra={"trace_id": ctx.trace_id}
                )
                path_result.cpe_exit_hop = 2
                path_result.split_point_hop = 3
            
            # 提取 CPE 之后的路径
            split_point = path_result.split_point_hop
            post_cpe_hops = [
                hop for hop in path_result.full_path 
                if hop.hop_number >= split_point
            ]
            path_result.post_cpe_hops = post_cpe_hops
            
            # 如果智能分析未生成指纹，则手动生成
            if not path_result.path_fingerprint:
                fingerprint_parts = []
                max_fingerprint_hops = 6
                
                for hop in post_cpe_hops[:max_fingerprint_hops]:
                    if hop.ip_addresses:
                        ip_str = hop.ip_addresses[0]
                    elif hop.is_timeout:
                        ip_str = "T"
                    else:
                        ip_str = "?"
                    
                    fingerprint_parts.append(f"{hop.hop_number}:{ip_str}")
                
                path_result.path_fingerprint = "->".join(fingerprint_parts) if fingerprint_parts else "无有效跳点"
            
            # 确定链路分类
            if "google" in domain.lower() or "youtube" in domain.lower():
                path_result.link_category = "international"
            elif "baidu" in domain.lower() or "taobao" in domain.lower():
                path_result.link_category = "domestic"
            else:
                path_result.link_category = "unknown"
            
            # 计算路径质量指标
            valid_rtts = []
            timeout_count = 0
            for hop in path_result.full_path:
                if hop.rtts:
                    valid_rtts.extend(hop.rtts)
                if hop.is_timeout:
                    timeout_count += 1
            
            if valid_rtts:
                path_result.avg_rtt_ms = sum(valid_rtts) / len(valid_rtts)
                path_result.max_rtt_ms = max(valid_rtts)
            
            path_result.timeout_hop_count = timeout_count
            path_result.total_hop_count = len(path_result.full_path)
            
            # 计算路径质量评分
            completeness_score = min(100, (path_result.total_hop_count / max_hops) * 100) if max_hops > 0 else 50
            rtt_score = max(0, 100 - (path_result.avg_rtt_ms / 10)) if path_result.avg_rtt_ms > 0 else 50
            stability_score = max(0, 100 - (timeout_count * 10))
            
            path_result.path_quality_score = (
                completeness_score * 0.4 + 
                rtt_score * 0.3 + 
                stability_score * 0.3
            )
            
            logger.debug(
                f"域名 {domain} 路径分析完成: "
                f"跳数={path_result.total_hop_count}, "
                f"平均RTT={path_result.avg_rtt_ms:.1f}ms, "
                f"超时跳={timeout_count}, "
                f"质量评分={path_result.path_quality_score:.1f}",
                extra={"trace_id": ctx.trace_id}
            )
            
        except Exception as e:
            logger.error(
                f"域名 {domain} 路径分析异常: {e}",
                extra={"trace_id": ctx.trace_id},
                exc_info=True
            )
            path_result.path_fingerprint = f"分析异常: {str(e)[:50]}"
            path_result.link_category = "error"
            path_result.confidence = 0.0
        
        finally:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                f"域名 {domain} 路径分析耗时: {elapsed_ms:.1f}ms",
                extra={"trace_id": ctx.trace_id}
            )
        
        return path_result
    
    @staticmethod
    def _detect_ip_version(ip: str) -> str:
        """检测IP地址版本
        
        Args:
            ip: IP地址字符串
            
        Returns:
            'IPv4'、'IPv6' 或 'unknown'
        """
        if not ip or ip in ["*", "T", "?"]:
            return "unknown"
        
        try:
            import ipaddress
            addr = ipaddress.ip_address(ip)
            if isinstance(addr, ipaddress.IPv4Address):
                return "IPv4"
            elif isinstance(addr, ipaddress.IPv6Address):
                return "IPv6"
        except ValueError:
            pass
        
        return "unknown"
    
    async def test_cpe_link_routing(
        self,
        domains: List[str] = None,
        max_hops: int = None,  # ✅ 修改：默认为None，启用智能计算
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
            domains: 测试域名列表（默认使用统一域名集 DEFAULT_TEST_DOMAINS）
            max_hops: traceroute 最大跳数（默认根据场景智能计算）
            cpe_exit_hop: CPE出口跳数（默认第2跳是CPE，从第3跳开始分析）
            ctx: 流程上下文（可选）

        Returns:
            CpeLinkRouteResult: CPE链路分流测试结果
        """
        import time
        import asyncio
        
        # ✅ 修复：使用统一域名集，避免硬编码导致的冲突
        from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS
        
        if domains is None:
            domains = DEFAULT_TEST_DOMAINS

        start_time = time.monotonic()
        result = CpeLinkRouteResult(total_domains_tested=len(domains))

        if not ctx:
            # 创建临时上下文
            import uuid
            ctx = FlowContext(trace_id=str(uuid.uuid4()))

        logger.info(
            f"开始CPE链路分流检测: {len(domains)}个目标域名（异步并发执行）",
            extra={"trace_id": ctx.trace_id},
        )

        try:
            # ✅ 步骤1: 使用 asyncio.gather 并发执行所有域名的路径分析
            # 这样可以大幅缩短总耗时，从串行 N×90秒 降低到并行 max(90秒)
            tasks = []
            for domain in domains:
                task = self._analyze_domain_path(
                    domain=domain,
                    max_hops=max_hops,
                    cpe_exit_hop=cpe_exit_hop,
                    ctx=ctx
                )
                tasks.append(task)
            
            # 并发执行所有任务，即使某个失败也不影响其他任务
            results_with_errors = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            domain_results = []
            for i, result_or_error in enumerate(results_with_errors):
                domain = domains[i]
                
                if isinstance(result_or_error, Exception):
                    # 任务执行异常
                    logger.warning(
                        f"域名 {domain} 路径分析异常: {result_or_error}",
                        extra={"trace_id": ctx.trace_id}
                    )
                    result.errors.append(f"域名 {domain} 分析失败: {str(result_or_error)}")
                    
                    # 创建错误结果对象
                    error_result = DomainPathAnalysisResult(
                        domain=domain,
                        resolved_ip="N/A",
                        ip_version="unknown",
                        full_path=[],
                        post_cpe_hops=[],
                        path_fingerprint=f"异常: {str(result_or_error)[:50]}",
                        link_category="error",
                        confidence=0.0
                    )
                    domain_results.append(error_result)
                else:
                    # 正常结果
                    domain_results.append(result_or_error)
                    logger.debug(
                        f"域名 {domain} 路径分析完成: fingerprint={result_or_error.path_fingerprint}",
                        extra={"trace_id": ctx.trace_id}
                    )

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

    async def test_cpe_link_routing_optimized(
        self,
        domains: List[str] = None,
        max_hops: int = None,
        cpe_exit_hop: int = 2,
        ctx: Optional[FlowContext] = None,
        use_cache: bool = True,
    ) -> CpeLinkRouteResult:
        """优化的CPE链路分流检测（支持结果缓存和复用）

        优化策略：
        1. 使用统一的域名目标集
        2. 检查 Context 中是否有 DNS 解析缓存，避免重复查询
        3. 检查 Context 中是否有 TCPing 结果缓存，避免重复探测
        4. 将 Traceroute 结果存入 Context，供报告生成使用

        Args:
            domains: 测试域名列表（默认使用统一域名集）
            max_hops: Traceroute最大跳数（None则智能计算）
            cpe_exit_hop: CPE出口跳数
            ctx: 流程上下文
            use_cache: 是否使用缓存（默认True）

        Returns:
            CpeLinkRouteResult: CPE链路分流测试结果
        """
        from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS
        
        # ✅ 使用统一域名集
        if domains is None:
            domains = DEFAULT_TEST_DOMAINS
        
        if not ctx:
            import uuid
            ctx = FlowContext(trace_id=str(uuid.uuid4()))
        
        # ✅ 检查 DNS/TCPing 缓存
        dns_cache_dict = ctx.get("dns_resolution_cache") if use_cache else None
        tcping_cache_dict = ctx.get("tcping_results_cache") if use_cache else None
        
        if dns_cache_dict:
            logger.info(
                f"使用DNS解析缓存: {len(dns_cache_dict)}个域名已缓存",
                extra={"trace_id": ctx.trace_id}
            )
        if tcping_cache_dict:
            logger.info(
                f"使用TCPing结果缓存: {len(tcping_cache_dict)}个目标已缓存",
                extra={"trace_id": ctx.trace_id}
            )
        
        # 执行标准测试
        result = await self.test_cpe_link_routing(
            domains=domains,
            max_hops=max_hops,
            cpe_exit_hop=cpe_exit_hop,
            ctx=ctx
        )
        
        # ✅ 将 Traceroute 结果转换为结构化缓存并存入 Context
        traceroute_entries: Dict[str, TracerouteResultEntry] = {}
        for domain_result in result.domain_results:
            entry = TracerouteResultEntry(
                domain=domain_result.domain,
                resolved_ip=domain_result.resolved_ip,
                ip_version=domain_result.ip_version,
                full_path=[hop.to_dict() if hasattr(hop, 'to_dict') else hop for hop in domain_result.full_path],
                path_fingerprint=domain_result.path_fingerprint,
                link_category=domain_result.link_category,
                confidence=domain_result.confidence,
                duration_ms=domain_result.total_duration_ms if hasattr(domain_result, 'total_duration_ms') else 0.0
            )
            traceroute_entries[domain_result.domain] = entry
        
        # 存入 Context 时转换为字典（保持兼容性）
        ctx.set("traceroute_results_cache", {
            k: v.to_dict() for k, v in traceroute_entries.items()
        })
        
        # ✅ 关键修复：将整个测试结果也存入 Context，供报告生成器使用
        ctx.set("cpe_link_routing_result", result)
        
        logger.info(
            f"Traceroute结果已缓存到Context（{len(traceroute_entries)}个域名），可供报告生成使用",
            extra={"trace_id": ctx.trace_id}
        )
        
        return result
