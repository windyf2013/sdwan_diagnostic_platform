"""
一键体检流程定义 - 精简版

优化目标：
1. 统一域名目标集，避免各阶段使用不同的测试目标
2. 精简为3个核心域名：baidu、youtube、tiktok
3. 实现结果共享机制，避免冗余的多次DNS解析和Ping测试
4. 快速体检模式，约60-90秒完成全流程
"""

from sdwan_desktop.flow.definitions.base import FlowDefinition, StepDefinition, RetryPolicy
from sdwan_desktop.core.types.flow_state import FlowStatus

# ==================== 统一域名目标集（精简版）====================
# 仅保留3个核心域名，覆盖国内/国际/视频场景
UNIFIED_DOMAIN_SET = {
    # 国内核心服务（代表国内链路质量）
    "domestic_core": [
        "www.baidu.com",      # 国内搜索引擎
    ],
    
    # 国际视频平台（代表高带宽场景+国际链路）
    "video_services": [
        "www.youtube.com",    # 国际视频平台
        "www.tiktok.com",     # 国际短视频+直播电商
    ],
}

# ==================== 域名集配置策略 ====================

# 精简模式：快速体检（3个域名，约60-90秒）✅ 当前使用
QUICK_TEST_DOMAINS = (
    UNIFIED_DOMAIN_SET["domestic_core"] +
    UNIFIED_DOMAIN_SET["video_services"]
)

# 默认使用精简模式（最快速度）
DEFAULT_TEST_DOMAINS = QUICK_TEST_DOMAINS

# ==================== 域名分类标签 ====================
# 用于报告展示和统计分析
DOMAIN_CATEGORIES = {
    # 国内域名
    "domestic": UNIFIED_DOMAIN_SET["domestic_core"],
    # 视频域名（含国际链路）
    "video": UNIFIED_DOMAIN_SET["video_services"],
}

# 反向映射：域名 → 分类
DOMAIN_TO_CATEGORY = {}
for category, domains in DOMAIN_CATEGORIES.items():
    for domain in domains:
        DOMAIN_TO_CATEGORY[domain] = category

QUICK_CHECK_FLOW = FlowDefinition(
    id="quick-check-v3",
    name="一键体检（精简版）",
    version="3.0.0",  # ✅ 版本号升级，反映域名集精简
    description="Windows客户端基础配置检查与连通性分析（4核心域名+结果共享+快速体检）",
    steps=[
        StepDefinition(
            id="step-collect",
            name="系统信息采集",
            description="采集网卡、路由、DNS等系统信息",
            handler="collector.collect_system_info",
            timeout_seconds=10
        ),
        StepDefinition(
            id="step-gateway",
            name="网关连通性测试",
            description="测试局域网网关可达性",
            handler="connectivity.test_gateway",
            depends_on=["step-collect"],
            timeout_seconds=10
        ),
        StepDefinition(
            id="step-internet",
            name="互联网连通性测试",
            description="测试公网可达性（复用DNS解析结果）",
            handler="connectivity.test_internet_optimized",
            depends_on=["step-gateway"],  # ✅ 调整：仅依赖网关测试
            timeout_seconds=30  # ✅ 优化：3个域名并发TCPing测试
        ),
        # ✅ 新增：连通性检查步骤，如果失败则标记跳过后续测试
        StepDefinition(
            id="step-connectivity-check",
            name="连通性检查结果验证",
            description="检查网关和互联网连通性，失败则标记跳过后续高级测试",
            handler="flow_control.check_connectivity",
            depends_on=["step-gateway", "step-internet"],
            timeout_seconds=5
        ),
        StepDefinition(
            id="step-dns-split",
            name="DNS分流测试",
            description="测试国内外DNS解析差异（复用DNS解析结果）",
            handler="dns_split.test_optimized",
            depends_on=["step-connectivity-check"],  # ✅ 依赖连通性检查
            timeout_seconds=60  # ✅ 优化：3域名×2DNS，降低超时
        ),
        StepDefinition(
            id="step-cpe-link-routing",
            name="CPE链路分流检测",
            description="通过traceroute检测CPE设备对不同目标域名的链路分流情况（复用DNS/TCPing结果）",
            handler="dns_split.test_cpe_link_routing_optimized",
            depends_on=["step-connectivity-check"],  # ✅ 依赖连通性检查
            timeout_seconds=110  # ✅ 按规范：7跳×5秒×3次+缓冲≈105秒
        ),
        StepDefinition(
            id="step-analyze",
            name="配置异常检测",
            description="执行诊断规则",
            handler="analyzer.analyze",
            depends_on=["step-dns-split", "step-cpe-link-routing"],
            timeout_seconds=10
        ),
        StepDefinition(
            id="step-conclusion",
            name="诊断结论生成",
            description="综合所有检测结果生成诊断",
            handler="analyzer.generate_conclusion",
            depends_on=["step-analyze"],
            timeout_seconds=5
        ),
        StepDefinition(
            id="step-report",
            name="报告生成",
            description="生成HTML诊断报告",
            handler="reporter.generate_html",
            depends_on=["step-conclusion"],
            timeout_seconds=15
        )
    ],
    config={
        "parallel_groups": [["step-gateway", "step-dns"]],
        "continue_on_error": True,
        "save_snapshots": True,
        "shared_context_keys": [
            "dns_resolution_cache",      # DNS解析缓存
            "tcping_results_cache",      # TCPing结果缓存
            "traceroute_results_cache",  # Traceroute结果缓存
            "unified_domain_set",        # 统一域名集
            "test_mode",                 # 测试模式（quick）
            "dns_split_result",          # ✅ DNS分流测试结果
            "cpe_link_routing_result"    # ✅ CPE链路分流检测结果
        ]
    }
)
