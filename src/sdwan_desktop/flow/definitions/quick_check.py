"""
一键体检流程定义
"""

from sdwan_desktop.flow.definitions.base import FlowDefinition, StepDefinition, RetryPolicy
from sdwan_desktop.core.types.flow_state import FlowStatus

QUICK_CHECK_FLOW = FlowDefinition(
    id="quick-check-v1",
    name="一键体检",
    version="1.0.0",
    description="Windows客户端基础配置检查与连通性分析",
    steps=[
        StepDefinition(
            id="step-collect",
            name="系统信息采集",
            description="采集Windows网络配置",
            handler="collector.collect",
            timeout_seconds=30,
            retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=1)
        ),
        StepDefinition(
            id="step-gateway",
            name="网关连通性测试",
            description="测试默认网关可达性",
            handler="connectivity.test_gateway",
            depends_on=["step-collect"],
            timeout_seconds=10
        ),
        StepDefinition(
            id="step-dns",
            name="DNS解析测试",
            description="测试DNS服务器解析能力",
            handler="connectivity.test_dns",
            depends_on=["step-collect"],
            timeout_seconds=15
        ),
        StepDefinition(
            id="step-internet",
            name="互联网连通性测试",
            description="测试公网可达性",
            handler="connectivity.test_internet",
            depends_on=["step-gateway", "step-dns"],
            timeout_seconds=20
        ),
        StepDefinition(
            id="step-dns-split",
            name="DNS分流测试",
            description="测试国内外DNS解析差异",
            handler="dns_split.test",
            depends_on=["step-dns"],
            timeout_seconds=15
        ),
        StepDefinition(
            id="step-cpe-link-routing",
            name="CPE链路分流检测",
            description="通过traceroute检测CPE设备对不同目标域名的链路分流情况",
            handler="dns_split.test_cpe_link_routing",
            depends_on=["step-collect"],
            timeout_seconds=120
        ),
        StepDefinition(
            id="step-analyze",
            name="配置异常检测",
            description="执行诊断规则",
            handler="analyzer.analyze",
            depends_on=["step-internet", "step-dns-split", "step-cpe-link-routing"],
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
        "save_snapshots": True
    }
)