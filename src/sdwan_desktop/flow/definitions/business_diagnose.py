"""
业务路径诊断流程定义 (business-diagnose)

与 ``quick_check`` / ``deep_dive`` 一致：步骤由 ``FlowDefinition`` 描述，CLI 通过 ``FlowRuntime`` 执行。

流程：PC 采集（可选）→ 本机业务 DNS/TCP 探测 → **联合前置校验** → 本机业务 RCA → CPE/拓扑联合（可选）
→ **Overlay 与策略分流证据链归纳**
"""

from sdwan_desktop.flow.definitions.base import FlowDefinition, StepDefinition

BUSINESS_DIAGNOSE_FLOW = FlowDefinition(
    id="business-diagnose-v1",
    name="业务路径诊断",
    version="1.0.0",
    description="本机业务 FQDN:端口探测；可选 CPE 联合与 Overlay/fwmark 策略分流证据链",
    steps=[
        StepDefinition(
            id="step-pc-collect",
            name="PC端信息采集",
            description="采集 Windows 网络快照（可由 --no-collect-pc 跳过）",
            handler="collector.collect_pc_optional",
            timeout_seconds=30,
        ),
        StepDefinition(
            id="step-biz-probe",
            name="业务域名端口探测",
            description="本机 DNS(A) + TCP + 可选 ICMP 路由追踪（声明目标；追踪为旁证）",
            handler="diagnosis.business_domain_port_probe",
            depends_on=["step-pc-collect"],
            timeout_seconds=240,
        ),
        StepDefinition(
            id="step-validate-joint-prereq",
            name="联合分析前置校验",
            description="探测未通过且未 --allow-probe-only 时，若未提供 CPE 参数则终止（退出码 2）",
            handler="diagnosis.business_validate_joint_prereq",
            depends_on=["step-biz-probe"],
            timeout_seconds=5,
        ),
        StepDefinition(
            id="step-biz-rca",
            name="本机业务RCA",
            description="基于观测与探针行的本机业务根因引擎",
            handler="diagnosis.business_rca_standalone",
            depends_on=["step-validate-joint-prereq"],
            timeout_seconds=30,
        ),
        StepDefinition(
            id="step-joint-cpe-topology",
            name="CPE联合采集与拓扑",
            description="若启用联合模式：CPE 采集、拓扑、拓扑后探测与 RootCauseEngine",
            handler="diagnosis.business_joint_followup",
            depends_on=["step-biz-rca"],
            timeout_seconds=300,
        ),
        StepDefinition(
            id="step-overlay-policy-flow",
            name="Overlay与策略分流证据链",
            description="归纳 vxlan/bind、fwmark、多路由表与多组网形态；不断言 underlay 线序",
            handler="diagnosis.overlay_policy_flow",
            depends_on=["step-joint-cpe-topology"],
            timeout_seconds=30,
        ),
    ],
    config={
        "parallel_groups": [],
        "continue_on_error": False,
        "save_snapshots": True,
        "shared_context_keys": [
            "business_outcome",
            "causes_local",
            "causes",
            "joint_done",
            "topology",
            "cpe_result",
            "targeted_probe",
            "overlay_policy_flow",
            "joint_needed",
            "_parallel_cpe_task",
        ],
    },
)
