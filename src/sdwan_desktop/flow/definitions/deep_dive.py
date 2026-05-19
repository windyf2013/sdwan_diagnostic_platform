"""
深度诊断流程定义 (DeepDive)

流程：PC采集 → CPE连接 → CPE采集 → 拓扑构建 → PC 业务探测 → CPE 拓扑后补采
→ Overlay/策略分流证据链 → 根因分析 → 报告生成
"""

from typing import Tuple

from sdwan_desktop.flow.definitions.base import FlowDefinition, StepDefinition, RetryPolicy

# 与 CLI/GUI 一致的默认业务目标（须在非 GUI 包中定义，供 agentctl-core 无 PySide6 时导入）。
DEEP_DIVE_DEFAULT_BIZ_TARGETS: Tuple[str, ...] = (
    "www.baidu.com:443",
    "www.youtube.com:443",
    "www.tiktok.com:443",
)

# PC 侧三域 traceroute 并行时墙钟约 max(单域)；单域 tracert 预算 ~90s。
BIZ_PROBE_STEP_TIMEOUT_SECONDS = 300
# CPE 拓扑后补采（依赖 PC 探测得到的 biz_target_ips）。
CPE_POST_PROBE_STEP_TIMEOUT_SECONDS = 180
# 历史单步合并上限（文档/对照用；Flow 已拆为 biz + cpe 两步）。
TARGETED_PROBE_STEP_TIMEOUT_SECONDS = (
    BIZ_PROBE_STEP_TIMEOUT_SECONDS + CPE_POST_PROBE_STEP_TIMEOUT_SECONDS
)

DEEP_DIVE_FLOW = FlowDefinition(
    id="deep-dive-v1",
    name="深度诊断",
    version="1.2.0",
    description="PC与CPE联合深度诊断；含 Overlay/fwmark 策略分流证据链与根因分析",
    steps=[
        StepDefinition(
            id="step-pc-collect",
            name="PC端信息采集",
            description="采集Windows系统网络配置",
            handler="collector.collect_pc",
            timeout_seconds=30,
            retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=1),
        ),
        StepDefinition(
            id="step-cpe-connect",
            name="CPE设备连接",
            description="建立SSH/TELNET连接到CPE",
            handler="cpe_collector.connect",
            depends_on=["step-pc-collect"],
            timeout_seconds=60,
            retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=5),
        ),
        StepDefinition(
            id="step-cpe-collect",
            name="CPE配置采集",
            description="执行命令并解析CPE配置",
            handler="cpe_collector.collect_config",
            depends_on=["step-pc-collect", "step-cpe-connect"],
            timeout_seconds=180,
        ),
        StepDefinition(
            id="step-topology-build",
            name="网络拓扑构建",
            description="基于PC和CPE数据构建网络拓扑图",
            handler="topology.build",
            depends_on=["step-pc-collect", "step-cpe-collect"],
            timeout_seconds=30,
        ),
        StepDefinition(
            id="step-biz-probe",
            name="PC侧业务探测",
            description=(
                "对默认/自定义业务目标做 PC 侧 DNS(A)+TCP+traceroute（链路分流证据）"
            ),
            handler="probe.biz",
            depends_on=["step-topology-build"],
            timeout_seconds=BIZ_PROBE_STEP_TIMEOUT_SECONDS,
        ),
        StepDefinition(
            id="step-cpe-post-probe",
            name="CPE拓扑后补采",
            description="按设备类型与 PC 探测结果执行 CPE 运行态补采命令",
            handler="probe.cpe_post",
            depends_on=["step-biz-probe"],
            timeout_seconds=CPE_POST_PROBE_STEP_TIMEOUT_SECONDS,
        ),
        StepDefinition(
            id="step-overlay-policy-flow",
            name="Overlay与策略分流证据链",
            description=(
                "基于 CPE 解析与拓扑后探测归纳：DNS/url-group→ipset→mangle MARK→ip rule 选表；"
                "vxlan 三层口与 tunnel bind 关系；多组网形态标签；不断言 underlay 线序封装"
            ),
            handler="diagnosis.overlay_policy_flow",
            depends_on=["step-cpe-post-probe"],
            timeout_seconds=15,
        ),
        StepDefinition(
            id="step-root-cause",
            name="根因分析",
            description="执行深度诊断规则识别根因",
            handler="analyzer.analyze_root_cause",
            depends_on=[
                "step-topology-build",
                "step-cpe-post-probe",
                "step-overlay-policy-flow",
            ],
            timeout_seconds=30,
        ),
        StepDefinition(
            id="step-report-gen",
            name="专业报告生成",
            description="生成包含拓扑图的HTML深度诊断报告",
            handler="reporter.generate_deep_dive_html",
            depends_on=["step-root-cause"],
            timeout_seconds=20,
        ),
    ],
    config={
        "parallel_groups": [],
        "continue_on_error": False,
        "save_snapshots": True,
        "shared_context_keys": [
            "overlay_policy_flow",
            "targeted_probe",
            "targeted_probe_pc",
            "cpe_result",
        ],
    },
)
