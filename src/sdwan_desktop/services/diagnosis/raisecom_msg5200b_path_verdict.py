"""Raisecom MSG5200B：路径证据聚合与 Overlay 门控（5200B-only）。

产品规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`` §3。
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
    EvidenceTier,
    JointOverlayDatapathGate,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_fib_evidence import (
    evaluate_fib_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    pc_matches_sdwan_policy_source_prefix,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session_path import (
    evaluate_session_path_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_url_group import (
    evaluate_url_group_priority_for_domain,
    probe_domain_from_targeted_data,
)

logger = logging.getLogger(__name__)


def build_joint_path_evidence_dict(
    targeted_probe: Optional[Dict[str, Any]],
    cpe: Optional[CpeConfiguration],
    topology_dict: Optional[Dict[str, Any]],
    gate: JointOverlayDatapathGate,
    declared_path_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """5200B 联合报告证据链：L1 会话 + L3 FIB + 可选路径分析（供模板 ``joint_path_evidence``）。"""
    tp = targeted_probe if isinstance(targeted_probe, dict) else None
    data = tp.get("data") if tp else {}
    data = data if isinstance(data, dict) else {}
    pc_ip = _pc_ip_from_topology(topology_dict)
    l1 = evaluate_session_path_evidence(data, cpe, pc_ip)
    l3 = evaluate_fib_evidence(data, cpe)
    trace_ev = analyze_business_trace_evidence(tp, cpe, topology_dict)
    tier_label = {
        "precise": "精确定位",
        "heuristic": "启发式",
        "underlay_only": "仅 Underlay",
    }.get(gate.evidence_tier, gate.evidence_tier)
    out: Dict[str, Any] = {
        "status": "ok",
        "rule_case": gate.rule_case,
        "evidence_tier": gate.evidence_tier,
        "evidence_tier_label": tier_label,
        "datapath_banner_short": (gate.datapath_banner or "")[:500],
        "l1_session": {
            "summary": l1.summary,
            "overlay_path_confirmed": l1.overlay_path_confirmed,
            "line_confirmed_count": l1.line_confirmed_count,
            "rule_branch": l1.rule_branch,
            "blob_all_dips_tunnel": l1.blob_all_dips_tunnel,
            "sample_lines": list(l1.sample_lines),
        },
        "l3_fib": {
            "summary": l3.summary,
            "fib_suggests_overlay": l3.fib_suggests_overlay,
            "egress_dev": l3.egress_dev,
            "table_id": l3.table_id,
            "next_hop": l3.next_hop,
            "biz_ip_in_ipset": l3.biz_ip_in_ipset,
            "ipset_hint": l3.ipset_hint,
            "excerpts": list(l3.excerpts),
        },
        "l5_trace": {
            "overlay_hop_observed": trace_ev.overlay_hop_observed,
            "narrative_hint": trace_ev.narrative_hint or "",
            "egress_shape": trace_ev.egress_shape or "",
        },
    }
    if isinstance(declared_path_analysis, dict) and declared_path_analysis:
        out["declared_business_path_analysis"] = declared_path_analysis
        reach = declared_path_analysis.get("reachability")
        if isinstance(reach, dict) and reach:
            out["reachability"] = reach
    return out


def _tier_banner_prefix(tier: EvidenceTier) -> str:
    if tier == "precise":
        return "【精确定位】"
    if tier == "heuristic":
        return "【启发式】"
    return ""


def _underlay_clause(egress_shape: str) -> str:
    if egress_shape == "wan_gateway":
        return " Underlay 形态：经 WAN 网关再入公网。"
    if egress_shape == "early_public":
        return " Underlay 形态：离开 CPE 后早期即为公网跳。"
    return ""


def _url_group_supplement(tp: Optional[Dict[str, Any]]) -> str:
    if not tp or not isinstance(tp, dict):
        return ""
    data = tp.get("data")
    if not isinstance(data, dict):
        return ""
    domain = probe_domain_from_targeted_data(data)
    if not domain:
        return ""
    raw = dict(data.get("raw_outputs") or {})
    rc = str(raw.get("running-config") or raw.get("show running-config") or "")
    verdict = evaluate_url_group_priority_for_domain(
        domain=domain, raw_outputs=raw, running_config=rc
    )
    return verdict.summary if verdict else ""


def _pc_ip_from_topology(topology_dict: Optional[Dict[str, Any]]) -> Optional[str]:
    if not topology_dict:
        return None
    pc_id = topology_dict.get("pc_node_id")
    if not pc_id:
        return None
    for n in topology_dict.get("nodes") or []:
        if isinstance(n, dict) and n.get("id") == pc_id and n.get("type") == "pc":
            return (n.get("ip_address") or "").strip() or None
    return None


def _suppress_detail(rule_case: str, l1_summary: str, l3_summary: str) -> str:
    if rule_case == "raisecom_no_conntrack_sampling":
        return "本轮对声明业务目的地址的 nf_conntrack 采样未见非空会话行。"
    if rule_case == "raisecom_underlay_no_overlay_evidence":
        parts = [
            "本轮 conntrack 已采样到声明目的地址会话，但未满足展示隧道示意的条件。",
            l1_summary,
            l3_summary,
        ]
        return " ".join(p for p in parts if p)
    return ""


def compute_raisecom_msg5200b_path_verdict(
    targeted_probe: Optional[Dict[str, Any]],
    cpe_configuration: Optional[CpeConfiguration],
    topology_dict: Optional[Dict[str, Any]],
) -> JointOverlayDatapathGate:
    """L0–L5 聚合 → ``JointOverlayDatapathGate``（废除 D0 公网 DIP）。"""
    tp = targeted_probe if isinstance(targeted_probe, dict) else None
    cpe = cpe_configuration
    url_sup = _url_group_supplement(tp)
    ug = f" {url_sup}" if url_sup else ""

    has_ct = targeted_probe_has_business_target_conntrack_hits(tp)
    data = tp.get("data") if tp else {}
    data = data if isinstance(data, dict) else {}
    pc_ip = _pc_ip_from_topology(topology_dict)

    trace_ev = analyze_business_trace_evidence(tp, cpe, topology_dict)
    egress_shape = compute_egress_shape(trace_ev, topology_dict)
    ul = _underlay_clause(egress_shape)

    if not has_ct:
        logger.info("raisecom_path_verdict: rule_case=raisecom_no_conntrack_sampling")
        return JointOverlayDatapathGate(
            show_overlay_tunnel_strip=False,
            overlay_evidence_positive=False,
            rule_case="raisecom_no_conntrack_sampling",
            evidence_tier="underlay_only",
            datapath_banner=(
                "【5200B · 会话】CPE 侧 nf_conntrack 对声明目的地址**采样不成功（无有效会话行）**："
                "按产品规则视为**会话不匹配**；可**精准判断**在本轮观测下业务流**未表现为经本设备转发**。"
                "故不展示 CPE↔Hub 隧道示意条。"
            ),
            joint_overlay_topology_note="",
            url_group_supplement=url_sup,
            presentation_suppress_detail=_suppress_detail(
                "raisecom_no_conntrack_sampling", "", ""
            ),
        )

    l1 = evaluate_session_path_evidence(data, cpe, pc_ip)
    l3 = evaluate_fib_evidence(data, cpe)
    policy_ok = pc_matches_sdwan_policy_source_prefix(pc_ip, cpe)

    if l1.overlay_path_confirmed and l1.line_confirmed_count > 0:
        rule = "raisecom_overlay_conntrack_bidirectional"
        logger.info("raisecom_path_verdict: rule_case=%s", rule)
        return JointOverlayDatapathGate(
            show_overlay_tunnel_strip=True,
            overlay_evidence_positive=True,
            rule_case=rule,
            evidence_tier="precise",
            egress_shape=egress_shape,
            datapath_banner=(
                f"{_tier_banner_prefix('precise')}【5200B · L1 会话】{l1.summary}"
                " 正向 dst 为业务目标且回程经 vxlan/隧道端点 → **判定走 Overlay**。"
                "本报告展示 CPE↔Hub 隧道示意条。"
                + ul
                + ug
            ),
            joint_overlay_topology_note=(
                "示意条在「conntrack 双向五元组 + vxlan 回程」条件下展示；"
                "仍须与 FIB/策略表交叉复核。"
            ),
            url_group_supplement=url_sup,
            presentation_suppress_detail="",
        )

    if l1.overlay_path_confirmed and l1.blob_all_dips_tunnel:
        rule = "raisecom_all_dip_tunnel_precise"
        logger.info("raisecom_path_verdict: rule_case=%s", rule)
        return JointOverlayDatapathGate(
            show_overlay_tunnel_strip=True,
            overlay_evidence_positive=True,
            rule_case=rule,
            evidence_tier="precise",
            egress_shape=egress_shape,
            datapath_banner=(
                f"{_tier_banner_prefix('precise')}【5200B · L1 会话】{l1.summary}"
                " → **判定一定走隧道/Overlay**。本报告展示隧道示意条。"
                + ul
                + ug
            ),
            joint_overlay_topology_note=(
                "「全 DIP 为隧道地址」成立时展示示意条；若与策略表不一致请人工复核。"
            ),
            url_group_supplement=url_sup,
            presentation_suppress_detail="",
        )

    if policy_ok:
        rule = "raisecom_session_matched_policy_prefix"
        logger.info("raisecom_path_verdict: rule_case=%s", rule)
        return JointOverlayDatapathGate(
            show_overlay_tunnel_strip=True,
            overlay_evidence_positive=True,
            rule_case=rule,
            evidence_tier="precise",
            egress_shape=egress_shape,
            datapath_banner=(
                f"{_tier_banner_prefix('precise')}【5200B · 策略源】nf_conntrack 采样成功且 "
                "**PC 与 SD-WAN 策略源前缀匹配**；"
                f"{l1.summary} {l3.summary}"
                "本报告展示 CPE↔Hub 隧道示意条。"
                + ul
                + ug
            ),
            joint_overlay_topology_note=(
                "示意条在「策略源匹配 + conntrack 命中」条件下展示；仍须与路由/专检交叉复核。"
            ),
            url_group_supplement=url_sup,
            presentation_suppress_detail="",
        )

    if l3.biz_ip_in_ipset and l3.fib_suggests_overlay:
        rule = "raisecom_policy_fib_overlay"
        logger.info("raisecom_path_verdict: rule_case=%s", rule)
        return JointOverlayDatapathGate(
            show_overlay_tunnel_strip=True,
            overlay_evidence_positive=True,
            rule_case=rule,
            evidence_tier="precise",
            egress_shape=egress_shape,
            datapath_banner=(
                f"{_tier_banner_prefix('precise')}【5200B · L2+L3】{l3.summary}"
                f" {l1.summary}"
                "本报告展示 CPE↔Hub 隧道示意条。"
                + ul
                + ug
            ),
            joint_overlay_topology_note=(
                "示意条在「ipset 命中 + FIB 出 vxlan」条件下展示。"
            ),
            url_group_supplement=url_sup,
            presentation_suppress_detail="",
        )

    if trace_ev.overlay_hop_observed:
        rule = "raisecom_trace_overlay_hop"
        logger.info("raisecom_path_verdict: rule_case=%s", rule)
        return JointOverlayDatapathGate(
            show_overlay_tunnel_strip=True,
            overlay_evidence_positive=True,
            rule_case=rule,
            evidence_tier="heuristic",
            egress_shape=egress_shape,
            datapath_banner=(
                f"{_tier_banner_prefix('heuristic')}【5200B · L5 跳表】nf_conntrack 采样成功；"
                "PC 侧 traceroute **可能**经隧道/Overlay 相关地址。"
                f" {l1.summary} {l3.summary}"
                + (f" {trace_ev.narrative_hint}" if trace_ev.narrative_hint else "")
                + ul
                + ug
            ),
            joint_overlay_topology_note=(
                "示意条在「跳表命中隧道/Overlay 地址」条件下展示；请与 conntrack、FIB 对照复核。"
            ),
            url_group_supplement=url_sup,
            presentation_suppress_detail="",
        )

    rule = "raisecom_underlay_no_overlay_evidence"
    trace_clause = ""
    if trace_ev.trace_available and trace_ev.egress_past_cpe:
        trace_clause = f" {trace_ev.narrative_hint}。"
    logger.info("raisecom_path_verdict: rule_case=%s", rule)
    detail = _suppress_detail(rule, l1.summary, l3.summary)
    return JointOverlayDatapathGate(
        show_overlay_tunnel_strip=False,
        overlay_evidence_positive=False,
        rule_case=rule,
        evidence_tier="underlay_only",
        egress_shape=egress_shape,
        datapath_banner=(
            "【Underlay】【5200B】nf_conntrack 采样成功；"
            f"{l1.summary} {l3.summary}"
            "按产品规则**不**将声明流与 CPE↔Hub 隧道面绑定展示。"
            + trace_clause
            + ul
            + ug
        ),
        joint_overlay_topology_note="",
        url_group_supplement=url_sup,
        presentation_suppress_detail=detail,
    )
