"""Raisecom MSG5200B：声明业务路径分析门面（5200B-only）。

单一事实源：``DeclaredBusinessPathAnalysis`` → 报告 / gate 只读映射。
规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md``。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.core.types.declared_business_path import (
    ConfidenceTier,
    DeclaredBusinessPathAnalysis,
    ReachabilityAnalysis,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_fib_evidence import (
    evaluate_fib_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_link_protect_evidence import (
    evaluate_link_protect_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_policy_chain_contrast import (
    build_raisecom_msg5200b_policy_chain_and_reconcile,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_reachability_evidence import (
    evaluate_reachability_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_url_group import (
    _merged_raw_outputs,
    build_raisecom_msg5200b_url_group_analysis,
    probe_domain_from_targeted_data,
)

logger = logging.getLogger(__name__)


def _pc_ip_from_topology(topology_dict: Optional[Dict[str, Any]]) -> Optional[str]:
    if not topology_dict:
        return None
    pc_id = topology_dict.get("pc_node_id")
    if not pc_id:
        return None
    for n in topology_dict.get("nodes") or []:
        if isinstance(n, dict) and n.get("id") == pc_id and n.get("type") == "pc":
            ip = (n.get("ip_address") or "").strip()
            return ip or None
    return None


def analyze_raisecom_msg5200b_declared_business_path(
    targeted_probe: Optional[Dict[str, Any]],
    cpe_configuration: Optional[CpeConfiguration],
    topology_dict: Optional[Dict[str, Any]] = None,
) -> DeclaredBusinessPathAnalysis:
    """联合 CPE 声明业务：url-group 分析 + 策略链对照 + 路径 reconcile。"""
    try:
        tp = targeted_probe if isinstance(targeted_probe, dict) else None
        if tp is None:
            return DeclaredBusinessPathAnalysis(
                status="partial",
                error="无 targeted_probe",
            )
        data = tp.get("data")
        if not isinstance(data, dict):
            return DeclaredBusinessPathAnalysis(
                status="partial",
                error="targeted_probe.data 无效",
            )

        domain = probe_domain_from_targeted_data(data)
        pc_ip = _pc_ip_from_topology(topology_dict)
        url_group = build_raisecom_msg5200b_url_group_analysis(
            domain=domain,
            targeted_data=data,
            cpe=cpe_configuration,
            pc_ip=pc_ip,
        )
        steps, reconcile, config_intent, observed = build_raisecom_msg5200b_policy_chain_and_reconcile(
            targeted_data=data,
            cpe=cpe_configuration,
            pc_ip=pc_ip,
            url_group=url_group,
        )

        raw = _merged_raw_outputs(data, cpe_configuration)
        l3 = evaluate_fib_evidence(data, cpe_configuration)
        eff_group = url_group.effective_group if url_group else None
        lp_ev = evaluate_link_protect_evidence(
            link_protect_blob=str(raw.get("show link-protect status") or ""),
            cpe=cpe_configuration,
            effective_group=eff_group,
            fib_egress_dev=l3.egress_dev,
        )
        if url_group is not None:
            url_group.link_protect_summary = lp_ev.summary

        ping_blobs = {
            k: str(v)
            for k, v in raw.items()
            if str(k).startswith("diagnose:ping") and v
        }
        reach_ev = evaluate_reachability_evidence(
            targeted_probe=tp,
            config_intent=config_intent,
            next_hop=l3.next_hop,
            egress_dev=l3.egress_dev,
            link_protect_action_down=lp_ev.action_iface_down,
            arp_blob=str(raw.get("show arp") or ""),
            ping_blobs=ping_blobs,
        )
        reachability = ReachabilityAnalysis(
            s1_status=reach_ev.s1_status,
            s1_summary=reach_ev.s1_summary,
            s2_status=reach_ev.s2_status,
            s2_summary=reach_ev.s2_summary,
            primary_rule_case=reach_ev.primary_rule_case,
            next_hop_checked=reach_ev.next_hop_checked,
        )
        if (
            reach_ev.s2_status == "unreachable"
            and reconcile.break_point is None
            and config_intent == "sdwan_overlay"
        ):
            reconcile.break_point = "next_hop_unreachable"
            reconcile.outcome = "mismatch"
            reconcile.primary_rule_case = (
                reach_ev.primary_rule_case or "raisecom_reachability_next_hop_unreachable"
            )
            reconcile.summary_for_delivery = reach_ev.s2_summary

        confidence: ConfidenceTier = "heuristic"
        if reconcile.outcome == "match" and reconcile.break_point is None:
            confidence = "precise"
        elif reconcile.outcome == "mismatch" and reconcile.break_point:
            confidence = "precise"
        elif reconcile.outcome == "insufficient_evidence":
            confidence = "unverified"

        if url_group and url_group.summary and not reconcile.summary_for_delivery:
            reconcile.summary_for_delivery = url_group.summary

        logger.info(
            "raisecom_path_analysis: config_intent=%s observed=%s outcome=%s break_point=%s",
            config_intent,
            observed,
            reconcile.outcome,
            reconcile.break_point,
        )
        return DeclaredBusinessPathAnalysis(
            status="ok",
            config_intent=config_intent,
            observed_plane=observed,
            confidence=confidence,
            url_group_analysis=url_group,
            policy_chain_contrast=steps,
            reachability=reachability,
            reconcile=reconcile,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("raisecom_path_analysis failed: %s", exc, exc_info=True)
        return DeclaredBusinessPathAnalysis(
            status="error",
            error=str(exc),
        )
