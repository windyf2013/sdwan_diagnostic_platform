"""业务联合报告：拓扑展示剖面（Underlay / Overlay）单一事实源。

避免 ``finalize_business_topology_joint_report`` 与 ``compute_joint_overlay_datapath_gate``、
``failure_beyond_sdwan_edge_likely``、``_annotate_problem_nodes`` 各自为政导致「互联网 Underlay + SD-WAN Overlay」
或「RCA 写域外、拓扑标 CPE 红」等自相矛盾。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.diagnosis.business_trace_evidence import (
    BusinessTraceEvidence,
    analyze_business_trace_evidence,
)
from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    targeted_probe_has_business_target_conntrack_hits,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    JointOverlayDatapathGate,
)
from sdwan_desktop.services.reporter.joint_commercial_delivery import (
    targeted_probe_business_rows_all_ok,
)

TopologyDisplayVariant = Literal["sdwan", "internet"]


def topology_has_cpe_hub_tunnel(topology_dict: Optional[Dict[str, Any]]) -> bool:
    if not topology_dict:
        return False
    cpe_id = topology_dict.get("cpe_node_id")
    hub_id = topology_dict.get("hub_node_id")
    if not cpe_id or not hub_id:
        return False
    for e in topology_dict.get("edges") or []:
        if not isinstance(e, dict):
            continue
        if (
            e.get("link_type") == "tunnel"
            and e.get("source_id") == cpe_id
            and e.get("target_id") == hub_id
        ):
            return True
    return False


@dataclass(frozen=True, slots=True)
class JointTopologyPresentation:
    """联合 HTML 拓扑区展示决策（只读，由证据链推导）。"""

    variant: TopologyDisplayVariant
    show_overlay_tunnel_strip: bool
    path_focus_beyond_sdwan: bool
    trim_underlay_at_first_problem_node: bool
    underlay_fault_on_internet_ingress: bool
    suppress_heuristic_cpe_underlay_markers: bool
    narrative_coherence_note: str


def resolve_joint_topology_presentation(
    *,
    topology_dict: Optional[Dict[str, Any]],
    targeted_probe: Optional[Dict[str, Any]],
    gate: JointOverlayDatapathGate,
    trace_ev: Optional[BusinessTraceEvidence] = None,
    cpe_configuration: Optional[CpeConfiguration] = None,
    business_probe_all_ok: Optional[bool] = None,
) -> JointTopologyPresentation:
    """由 ``JointOverlayDatapathGate`` + 路径旁证推导展示剖面（唯一入口）。

  **产品原则**（与 ``docs/rules/.../raisecom_msg5200b_network_analysis.md`` §5.2 一致）：

  - **展示 CPE↔Hub Overlay 条带**：仅当 ``gate.show_overlay_tunnel_strip`` 为真（策略源匹配 /
    conntrack 全 DIP 为隧道地址 / traceroute 命中 Overlay 地址等），**与探测通不通无关**。
  - **不得**因「设备配置存在隧道边」「conntrack 命中公网目的 IP」「traceroute 已出站到公网
    (egress_past_cpe)」单独展示 Overlay——后者表示 Underlay/公网路径，与隧道无关。
    """
    tp = targeted_probe if isinstance(targeted_probe, dict) else None

    te = trace_ev or analyze_business_trace_evidence(tp, cpe_configuration, topology_dict)
    has_ct = targeted_probe_has_business_target_conntrack_hits(tp)
    biz_ok = (
        business_probe_all_ok
        if business_probe_all_ok is not None
        else targeted_probe_business_rows_all_ok(tp)
    )

    show_overlay = bool(gate.show_overlay_tunnel_strip)
    variant: TopologyDisplayVariant = "sdwan" if show_overlay else "internet"

    # 已离开 CPE 且未绑定 Overlay：用于抑制 CPE 启发式标红（与探测通不通无关）。
    path_beyond = bool(
        show_overlay is False
        and te.trace_available
        and te.egress_past_cpe
        and has_ct
    )

    note_parts: list[str] = []
    if show_overlay:
        note_parts.append("SD-WAN 联合剖面：Underlay 为 PC→出口→公网目标域示意；隧道对端 Hub 仅在 Overlay 条带展示。")
    else:
        note_parts.append(
            "互联网/Underlay 剖面：不展示 CPE↔Hub 隧道条带（本轮未满足「声明流与 Overlay 面观测关联」门槛）。"
        )
    if path_beyond:
        if biz_ok:
            note_parts.append(
                "路径旁证表明报文已离开 CPE/站点私网域；Underlay 示意至公网目标域"
                "（本机探测已通过，不在 CPE/Hub 上标红）。"
            )
        else:
            note_parts.append(
                "路径旁证表明报文已离开 CPE/站点私网域；Underlay 不在 CPE/Hub 上标红，"
                "故障段示意为出口→公网目标域。"
            )

    return JointTopologyPresentation(
        variant=variant,
        show_overlay_tunnel_strip=show_overlay,
        path_focus_beyond_sdwan=path_beyond,
        trim_underlay_at_first_problem_node=not path_beyond,
        underlay_fault_on_internet_ingress=path_beyond and not biz_ok,
        suppress_heuristic_cpe_underlay_markers=path_beyond or (has_ct and te.egress_past_cpe),
        narrative_coherence_note=" ".join(note_parts),
    )
