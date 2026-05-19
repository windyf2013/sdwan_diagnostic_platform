"""非 Raisecom 5200B：business-diagnose 联合 Overlay 门控（通用回退）。

规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`` §6。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.diagnosis.business_trace_evidence import (
    analyze_business_trace_evidence,
    compute_egress_shape,
)
from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    targeted_probe_has_business_target_conntrack_hits,
)
from sdwan_desktop.services.diagnosis.joint_overlay_datapath_gate import (
    JointOverlayDatapathGate,
)

logger = logging.getLogger(__name__)


def compute_generic_joint_overlay_gate(
    targeted_probe: Optional[Dict[str, Any]],
    cpe_configuration: Optional[CpeConfiguration],
    topology_dict: Optional[Dict[str, Any]],
) -> JointOverlayDatapathGate:
    """仅 traceroute 命中隧道/Overlay 时展示示意条；conntrack 公网命中不足以打开 Overlay。"""
    tp = targeted_probe if isinstance(targeted_probe, dict) else None
    has_ct = targeted_probe_has_business_target_conntrack_hits(tp)
    trace_ev = analyze_business_trace_evidence(tp, cpe_configuration, topology_dict)
    egress_shape = compute_egress_shape(trace_ev, topology_dict)

    if trace_ev.overlay_hop_observed:
        note = "跳表命中隧道/Overlay 相关地址，展示 CPE↔Hub 示意条（仍须与策略/专检交叉复核）。"
        if trace_ev.trace_available:
            note += f" {trace_ev.narrative_hint}"
        logger.info("generic_joint_overlay_gate: branch=non_raisecom_trace_overlay_hop")
        return JointOverlayDatapathGate(
            show_overlay_tunnel_strip=True,
            overlay_evidence_positive=True,
            rule_case="non_raisecom_trace_overlay_hop",
            evidence_tier="heuristic",
            egress_shape=egress_shape,
            datapath_banner=(
                "【启发式】【路径实证】PC 侧 traceroute 跳表命中隧道/Overlay 相关地址；"
                "本报告展示 CPE↔Hub 隧道示意条（组网示意，非形式化转发证明）。"
                + (f" {trace_ev.narrative_hint}" if trace_ev.narrative_hint else "")
            ),
            joint_overlay_topology_note=note,
        )

    trace_clause = ""
    if trace_ev.trace_available and trace_ev.egress_past_cpe:
        trace_clause = f" {trace_ev.narrative_hint}。"
    underlay_note = _underlay_shape_note(egress_shape)
    logger.info("generic_joint_overlay_gate: branch=non_raisecom_no_overlay_evidence")
    return JointOverlayDatapathGate(
        show_overlay_tunnel_strip=False,
        overlay_evidence_positive=False,
        rule_case="non_raisecom_no_overlay_evidence",
        evidence_tier="underlay_only",
        egress_shape=egress_shape,
        datapath_banner=(
            "【Underlay】"
            + (
                "CPE 上对声明目的地址的 nf_conntrack 采样存在非空行，"
                if has_ct
                else "CPE 上对声明目的地址的 nf_conntrack 采样未见非空行，"
            )
            + "但未观察到跳表命中隧道/Overlay 地址"
            + (trace_clause if trace_clause else "。")
            + underlay_note
            + "按产品规则**不**将声明流与 CPE↔Hub 隧道面绑定展示。"
        ),
        joint_overlay_topology_note="",
    )


def _underlay_shape_note(egress_shape: str) -> str:
    if egress_shape == "wan_gateway":
        return " Underlay 形态：经 WAN 网关再入公网。"
    if egress_shape == "early_public":
        return " Underlay 形态：离开 CPE 后早期即为公网跳。"
    return ""
