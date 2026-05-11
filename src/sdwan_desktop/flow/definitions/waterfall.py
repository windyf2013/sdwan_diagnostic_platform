"""
Waterfall 性能分析流程定义

遵循 SDWAN_SPEC.md §2.3 流程编排规范
"""

from sdwan_desktop.flow.definitions.base import FlowDefinition, StepDefinition, RetryPolicy
from sdwan_desktop.core.types.flow_state import FlowStatus

WATERFALL_FLOW = FlowDefinition(
    id="waterfall-analysis-v1",
    name="Web性能瀑布流分析",
    version="1.0.0",
    description="基于 Playwright 采集 HAR 并进行深度性能瓶颈分析",
    steps=[
        StepDefinition(
            id="step-har-capture",
            name="HAR采集",
            description="使用 Playwright 录制目标页面的网络请求 HAR 文件",
            handler="tools.har_capture.execute",
            timeout_seconds=120,
            retry_policy=RetryPolicy(max_attempts=1)
        ),
        StepDefinition(
            id="step-har-parse",
            name="HAR解析",
            description="解析 HAR JSON 文件为标准化 WaterfallResult 数据模型",
            handler="parser.har_parser.parse",
            depends_on=["step-har-capture"],
            timeout_seconds=15
        ),
        StepDefinition(
            id="step-perf-analyze",
            name="性能摘要分析",
            description="识别最慢资源及渲染阻塞项",
            handler="analyzer.perf_analyzer.analyze",
            depends_on=["step-har-parse"],
            timeout_seconds=10
        ),
        StepDefinition(
            id="step-rule-check",
            name="性能规则匹配",
            description="执行 7 条性能诊断规则 (PERF-001 ~ PERF-007)",
            handler="analyzer.rules.performance.check_all",
            depends_on=["step-har-parse"],
            timeout_seconds=10
        ),
        StepDefinition(
            id="step-report-generate",
            name="报告生成",
            description="生成包含瀑布流图表和诊断结论的 HTML 报告",
            handler="reporter.report_generator.generate_waterfall_report",
            depends_on=["step-perf-analyze", "step-rule-check"],
            timeout_seconds=20
        )
    ]
)
