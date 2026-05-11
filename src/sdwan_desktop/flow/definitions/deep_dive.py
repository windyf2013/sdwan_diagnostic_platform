"""
深度诊断流程定义 (DeepDive)

流程：PC采集 → CPE连接 → CPE采集 → 配置解析 → 拓扑构建 → 根因分析 → 报告生成
"""

from sdwan_desktop.flow.definitions.base import FlowDefinition, StepDefinition, RetryPolicy

DEEP_DIVE_FLOW = FlowDefinition(
    id="deep-dive-v1",
    name="深度诊断",
    version="1.0.0",
    description="PC与CPE联合深度诊断，包含拓扑构建与根因分析",
    steps=[
        StepDefinition(
            id="step-pc-collect",
            name="PC端信息采集",
            description="采集Windows系统网络配置",
            handler="collector.collect_pc",
            timeout_seconds=30,
            retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=1)
        ),
        StepDefinition(
            id="step-cpe-connect",
            name="CPE设备连接",
            description="建立SSH/TELNET连接到CPE",
            handler="cpe_collector.connect",
            depends_on=["step-pc-collect"],
            timeout_seconds=60,
            retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=5)
        ),
        StepDefinition(
            id="step-cpe-collect",
            name="CPE配置采集",
            description="执行命令并解析CPE配置",
            handler="cpe_collector.collect_config",
            depends_on=["step-pc-collect", "step-cpe-connect"],
            timeout_seconds=120
        ),
        StepDefinition(
            id="step-topology-build",
            name="网络拓扑构建",
            description="基于PC和CPE数据构建网络拓扑图",
            handler="topology.build",
            depends_on=["step-pc-collect", "step-cpe-collect"],
            timeout_seconds=30
        ),
        StepDefinition(
            id="step-root-cause",
            name="根因分析",
            description="执行深度诊断规则识别根因",
            handler="analyzer.analyze_root_cause",
            depends_on=["step-topology-build"],
            timeout_seconds=30
        ),
        StepDefinition(
            id="step-report-gen",
            name="专业报告生成",
            description="生成包含拓扑图的HTML深度诊断报告",
            handler="reporter.generate_deep_dive_html",
            depends_on=["step-root-cause"],
            timeout_seconds=20
        )
    ],
    config={
        "parallel_groups": [],
        "continue_on_error": False,
        "save_snapshots": True
    }
)
