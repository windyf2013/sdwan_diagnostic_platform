"""business-diagnose 联合拓扑字典：门控 + 5200B 声明路径分析（编排瘦身入口）。

CLI 与仿真矩阵共用，避免 ``business_diagnose.py`` 内重复拼装。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    targeted_probe_has_business_target_conntrack_hits,
)
from sdwan_desktop.services.diagnosis.joint_overlay_datapath_gate import (
    JointOverlayDatapathGate,
    compute_joint_overlay_datapath_gate,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    is_raisecom_msg5200b_cpe,
)


def apply_joint_datapath_and_path_analysis(
    topo_dict: Dict[str, Any],
    targeted_probe: Optional[Dict[str, Any]],
    cpe_configuration: Optional[CpeConfiguration],
) -> JointOverlayDatapathGate:
    """向 ``topo_dict`` 写入门控、5200B ``declared_business_path_analysis`` 与 ``joint_path_evidence``。"""
    gate = compute_joint_overlay_datapath_gate(
        targeted_probe if isinstance(targeted_probe, dict) else None,
        cpe_configuration,
        topo_dict,
    )
    tp_dict = targeted_probe if isinstance(targeted_probe, dict) else None
    has_ct = targeted_probe_has_business_target_conntrack_hits(tp_dict)
    topo_dict["declared_business_datapath_verdict"] = (
        "overlay_evidence_positive" if gate.overlay_evidence_positive else "unverified"
    )
    topo_dict["report_joint_nf_conntrack_had_session_lines"] = has_ct
    topo_dict["business_joint_suppress_overlay_topology_presentation"] = (
        not gate.show_overlay_tunnel_strip
    )
    if gate.show_overlay_tunnel_strip:
        topo_dict["joint_overlay_suppress_reason"] = ""
    elif getattr(gate, "presentation_suppress_detail", ""):
        topo_dict["joint_overlay_suppress_reason"] = gate.presentation_suppress_detail
    elif has_ct:
        topo_dict["joint_overlay_suppress_reason"] = (
            "本轮 conntrack 已采样到声明目的地址会话，但未满足产品规则中展示隧道示意的条件。"
            "请结合会话双向元组、FIB 表 99/100 与 traceroute 跳表明细复核。"
        )
    else:
        topo_dict["joint_overlay_suppress_reason"] = (
            "本轮对声明业务目的地址的 nf_conntrack 采样未见非空会话行"
        )
    topo_dict["declared_business_datapath_banner"] = gate.datapath_banner
    topo_dict["joint_overlay_topology_note"] = gate.joint_overlay_topology_note
    topo_dict["joint_overlay_rule_case"] = gate.rule_case
    topo_dict["joint_evidence_tier"] = gate.evidence_tier
    topo_dict["joint_egress_shape"] = gate.egress_shape
    topo_dict["show_business_flow_overlay"] = gate.show_business_flow_overlay
    if gate.url_group_supplement:
        topo_dict["url_group_priority_supplement"] = gate.url_group_supplement

    if cpe_configuration is not None and is_raisecom_msg5200b_cpe(cpe_configuration):
        from sdwan_desktop.services.diagnosis.raisecom_msg5200b_declared_path_analysis import (
            analyze_raisecom_msg5200b_declared_business_path,
        )
        from sdwan_desktop.services.diagnosis.raisecom_msg5200b_path_verdict import (
            build_joint_path_evidence_dict,
        )

        path_analysis = analyze_raisecom_msg5200b_declared_business_path(
            tp_dict, cpe_configuration, topo_dict
        )
        path_analysis_dict = path_analysis.to_template_dict()
        topo_dict["declared_business_path_analysis"] = path_analysis_dict
        if path_analysis.url_group_analysis and path_analysis.url_group_analysis.summary:
            topo_dict["url_group_priority_supplement"] = path_analysis.url_group_analysis.summary
        if path_analysis.reconcile.summary_for_delivery:
            topo_dict["path_reconcile_summary"] = path_analysis.reconcile.summary_for_delivery
        topo_dict["joint_path_evidence"] = build_joint_path_evidence_dict(
            tp_dict,
            cpe_configuration,
            topo_dict,
            gate,
            declared_path_analysis=path_analysis_dict,
        )

    return gate
