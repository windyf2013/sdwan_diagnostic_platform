"""Raisecom MSG5200B：声明业务策略链配置—运行对照（5200B-only）。

产品规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`` 路径对账 §。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.core.types.declared_business_path import (
    ConfigIntent,
    ObservedPlane,
    PathReconcileResult,
    PolicyChainStep,
    ReconcileOutcome,
    StepStatus,
    UrlGroupAnalysis,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_fib_evidence import (
    evaluate_fib_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_link_protect_evidence import (
    evaluate_link_protect_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_mangle_evidence import (
    evaluate_mangle_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session_path import (
    evaluate_session_path_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_url_group import (
    _merged_raw_outputs,
)

logger = logging.getLogger(__name__)


def _step(
    stage_id: str,
    *,
    config_status: StepStatus = "unknown",
    runtime_status: StepStatus = "unknown",
    config_excerpt: str = "",
    runtime_excerpt: str = "",
    narrative: str = "",
) -> PolicyChainStep:
    return PolicyChainStep(
        stage_id=stage_id,
        config_status=config_status,
        runtime_status=runtime_status,
        config_excerpt=config_excerpt[:500],
        runtime_excerpt=runtime_excerpt[:500],
        narrative=narrative,
    )


def _observed_plane_from_evidence(
    l1_overlay: bool,
    fib_overlay: bool,
) -> ObservedPlane:
    if l1_overlay or fib_overlay:
        return "overlay"
    if not l1_overlay and not fib_overlay:
        return "underlay"
    return "unknown"


def build_raisecom_msg5200b_policy_chain_and_reconcile(
    *,
    targeted_data: Dict[str, Any],
    cpe: Optional[CpeConfiguration],
    pc_ip: Optional[str],
    url_group: Optional[UrlGroupAnalysis],
) -> Tuple[List[PolicyChainStep], PathReconcileResult, ConfigIntent, ObservedPlane]:
    """构建策略链步骤与路径 reconcile（与 break_point 同源）。"""
    steps: List[PolicyChainStep] = []
    reconcile = PathReconcileResult()

    if url_group is None or not url_group.domain_matched:
        config_intent: ConfigIntent = "internet_underlay"
        steps.append(
            _step(
                "url_group",
                config_status="miss",
                runtime_status="miss",
                narrative="声明域未列入任一 url-group，预期 main/ge1 Underlay。",
            )
        )
    else:
        config_intent = "sdwan_overlay"
        names = [g.name for g in url_group.matched_groups]
        steps.append(
            _step(
                "url_group",
                config_status="match",
                runtime_status="match",
                config_excerpt=url_group.effective_selection_reason[:400],
                narrative=(
                    f"声明域在 url-group {names}；生效组「{url_group.effective_group}」。"
                    f" {url_group.policy_intent_one_liner}"
                ),
            )
        )

    l1 = evaluate_session_path_evidence(targeted_data, cpe, pc_ip)
    l3 = evaluate_fib_evidence(targeted_data, cpe)
    raw = _merged_raw_outputs(targeted_data, cpe)
    ipset_blob = str(raw.get("diagnose:ipset --list") or "")[:400]

    in_ipset = l3.biz_ip_in_ipset
    steps.append(
        _step(
            "ipset",
            config_status="match" if config_intent == "sdwan_overlay" else "not_applicable",
            runtime_status="match" if in_ipset else "miss",
            runtime_excerpt=ipset_blob[:300] if ipset_blob else "",
            narrative=l3.ipset_hint or l3.summary,
        )
    )

    break_point: Optional[str] = None
    eff_group = url_group.effective_group if url_group else None
    eff_sec = None
    if url_group and eff_group:
        for row in url_group.per_group_security:
            if row.group == eff_group:
                eff_sec = row
                break

    if config_intent == "sdwan_overlay" and eff_sec is not None:
        if not eff_sec.security_ip_enabled:
            steps.append(
                _step(
                    "security_src",
                    config_status="not_applicable",
                    runtime_status="not_applicable",
                    narrative=f"生效组「{eff_group}」未启用 security-ip，源地址不参与该组限制。",
                )
            )
        elif eff_sec.pc_in_list is True:
            steps.append(
                _step(
                    "security_src",
                    config_status="match",
                    runtime_status="match",
                    config_excerpt=f"PC {pc_ip}",
                    narrative=f"本机源 {pc_ip} 在「{eff_group}」security-ip 名单中。",
                )
            )
        elif eff_sec.pc_in_list is False:
            steps.append(
                _step(
                    "security_src",
                    config_status="match",
                    runtime_status="miss",
                    config_excerpt=f"PC {pc_ip}",
                    narrative=(
                        f"声明域在 url-group「{eff_group}」列表中且该组启用 security-ip；"
                        f"本机源 {pc_ip} 不在该组 security-ip 名单，未命中该组策略。"
                    ),
                )
            )
            break_point = "source_not_in_url_group_security_ip"
        else:
            steps.append(
                _step(
                    "security_src",
                    config_status="unknown",
                    runtime_status="unknown",
                    narrative="security-ip 或 PC 地址未知，无法精确定位源校验。",
                )
            )
    elif config_intent == "internet_underlay":
        steps.append(
            _step(
                "security_src",
                config_status="not_applicable",
                runtime_status="not_applicable",
                narrative="未配置 SD-WAN url-group 意图，跳过 security-ip 校验。",
            )
        )

    eff_meta = None
    if url_group and eff_group:
        for g in url_group.matched_groups:
            if g.name == eff_group:
                eff_meta = g
                break

    security_chain_ok = False
    if config_intent == "internet_underlay":
        security_chain_ok = False
    elif eff_sec is not None and not eff_sec.security_ip_enabled:
        security_chain_ok = True
    elif eff_sec is not None and eff_sec.pc_in_list is True:
        security_chain_ok = True

    mangle_blob = str(raw.get("diagnose:iptables -t mangle -nvL") or "")
    ip_rule_blob = str(raw.get("diagnose:ip rule show") or "")
    mangle_ev = evaluate_mangle_evidence(
        mangle_blob=mangle_blob,
        ip_rule_blob=ip_rule_blob,
        effective_group=eff_group,
        fwmark_hint=eff_meta.fwmark_hint if eff_meta else "",
        table_hint=eff_meta.table_hint if eff_meta else "",
        security_chain_ok=security_chain_ok,
        ipset_hit=in_ipset,
    )

    if break_point == "source_not_in_url_group_security_ip":
        steps.append(
            _step(
                "mangle",
                config_status="not_applicable",
                runtime_status="miss",
                runtime_excerpt="\n".join(mangle_ev.excerpts[:2]),
                narrative="security-ip 未命中，未进入该组 mangle MARK 规则。",
            )
        )
    elif config_intent == "internet_underlay":
        steps.append(
            _step(
                "mangle",
                config_status="not_applicable",
                runtime_status="not_applicable",
                narrative="无 SD-WAN url-group 意图，不要求 mangle 打标。",
            )
        )
    elif not mangle_ev.blob_present:
        steps.append(
            _step(
                "mangle",
                config_status="unknown",
                runtime_status="unknown",
                narrative=mangle_ev.summary,
            )
        )
    elif mangle_ev.mark_rule_matched:
        steps.append(
            _step(
                "mangle",
                config_status="match",
                runtime_status="match",
                config_excerpt=f"期望 MARK {mangle_ev.expected_mark}",
                runtime_excerpt="\n".join(mangle_ev.excerpts[:2]),
                narrative=mangle_ev.summary,
            )
        )
    else:
        steps.append(
            _step(
                "mangle",
                config_status="match" if mangle_ev.expected_mark else "unknown",
                runtime_status="miss",
                config_excerpt=f"期望 MARK {mangle_ev.expected_mark}",
                runtime_excerpt="\n".join(mangle_ev.excerpts[:2]),
                narrative=mangle_ev.summary,
            )
        )
        if (
            security_chain_ok
            and in_ipset
            and not break_point
            and mangle_ev.expected_mark
        ):
            break_point = "mangle_miss_or_wrong_mark"
        elif (
            security_chain_ok
            and mangle_ev.observed_mark_with_traffic
            and mangle_ev.expected_mark
            and mangle_ev.observed_mark_with_traffic != mangle_ev.expected_mark
            and not break_point
        ):
            break_point = "mangle_wrong_mark"

    if mangle_ev.ip_rule_excerpt:
        steps.append(
            _step(
                "ip_rule",
                config_status="match" if mangle_ev.expected_mark else "unknown",
                runtime_status="match" if mangle_ev.ip_rule_excerpt else "miss",
                config_excerpt=f"fwmark {mangle_ev.expected_mark} → table {mangle_ev.expected_table}",
                runtime_excerpt=mangle_ev.ip_rule_excerpt,
                narrative="ip rule 与期望 fwmark/表一致。" if mangle_ev.ip_rule_excerpt else "未见 ip rule。",
            )
        )
    elif config_intent == "sdwan_overlay" and mangle_ev.expected_mark:
        steps.append(
            _step(
                "ip_rule",
                config_status="match",
                runtime_status="unknown",
                narrative="未采集 ip rule 或无法匹配 fwmark 行。",
            )
        )

    lp_blob = str(raw.get("show link-protect status") or "")
    lp_ev = evaluate_link_protect_evidence(
        link_protect_blob=lp_blob,
        cpe=cpe,
        effective_group=eff_group,
        fib_egress_dev=l3.egress_dev,
    )

    if config_intent == "internet_underlay":
        steps.append(
            _step(
                "overlay_iface",
                config_status="not_applicable",
                runtime_status="not_applicable",
                narrative="互联网意图，不要求 vxlan link-protect。",
            )
        )
    elif not lp_ev.blob_present:
        steps.append(
            _step(
                "overlay_iface",
                config_status="unknown",
                runtime_status="unknown",
                narrative=lp_ev.summary,
            )
        )
    elif lp_ev.action_iface_down:
        steps.append(
            _step(
                "overlay_iface",
                config_status="match",
                runtime_status="miss",
                runtime_excerpt="\n".join(lp_ev.excerpts[:3]),
                config_excerpt=", ".join(lp_ev.expected_vxlans[:2]),
                narrative=lp_ev.summary,
            )
        )
        if config_intent == "sdwan_overlay" and not break_point:
            break_point = "overlay_iface_down_link_protect"
    else:
        steps.append(
            _step(
                "overlay_iface",
                config_status="match",
                runtime_status="match",
                runtime_excerpt="\n".join(lp_ev.excerpts[:3]),
                narrative=lp_ev.summary,
            )
        )

    steps.append(
        _step(
            "fib",
            config_status="unknown",
            runtime_status="match" if l3.fib_suggests_overlay else "miss",
            runtime_excerpt="; ".join(l3.excerpts[:3]),
            narrative=l3.summary,
        )
    )
    steps.append(
        _step(
            "session",
            config_status="unknown",
            runtime_status="match" if l1.overlay_path_confirmed else "miss",
            runtime_excerpt="\n".join(l1.sample_lines[:2]),
            narrative=l1.summary,
        )
    )

    observed = _observed_plane_from_evidence(l1.overlay_path_confirmed, l3.fib_suggests_overlay)
    outcome: ReconcileOutcome = "insufficient_evidence"
    primary = ""
    summary = ""

    if break_point == "source_not_in_url_group_security_ip" and eff_group:
        outcome = "mismatch"
        primary = "raisecom_path_mismatch_policy_not_applied"
        summary = (
            f"配置意图为 url-group「{eff_group}」走 SD-WAN，但 security-ip 未命中，"
            f"实然出口为 Underlay（{l3.egress_dev or 'main/ge1'}）。"
        )
    elif break_point == "overlay_iface_down_link_protect" and eff_group:
        outcome = "mismatch"
        primary = "raisecom_path_mismatch_policy_not_applied"
        summary = (
            f"配置意图为「{eff_group}」走 Overlay，但 link-protect/出接口 down，"
            f"实然 Underlay（{l3.egress_dev or 'main/ge1'}）。"
        )
    elif break_point == "next_hop_unreachable":
        outcome = "mismatch"
        primary = "raisecom_reachability_next_hop_unreachable"
        summary = (
            f"配置意图为 SD-WAN，但下一跳 {l3.next_hop or '—'} 不可达"
            f"（出接口 {l3.egress_dev or '—'}）。"
        )
    elif break_point in ("mangle_miss_or_wrong_mark", "mangle_wrong_mark") and eff_group:
        outcome = "mismatch"
        primary = "raisecom_path_mismatch_policy_not_applied"
        if break_point == "mangle_wrong_mark":
            summary = (
                f"配置意图为「{eff_group}」MARK {mangle_ev.expected_mark}，"
                f"观测到其它 MARK {mangle_ev.observed_mark_with_traffic} 有计数。"
            )
        else:
            summary = (
                f"配置意图为「{eff_group}」应打 MARK {mangle_ev.expected_mark}，"
                f"mangle 未见有效计数，实然 Underlay（{l3.egress_dev or 'main/ge1'}）。"
            )
    elif config_intent == "sdwan_overlay" and observed == "overlay":
        outcome = "match"
        primary = "raisecom_path_match_sdwan_overlay"
        summary = f"配置意图与运行面一致：走 Overlay（{l3.egress_dev or 'vxlan'}）。"
    elif config_intent == "internet_underlay" and observed == "underlay":
        outcome = "match"
        primary = "raisecom_path_match_internet_underlay"
        summary = f"未列入 url-group，实然走 Underlay（{l3.egress_dev or 'ge1'}）。"
    elif config_intent == "sdwan_overlay" and observed == "underlay":
        outcome = "mismatch"
        primary = "raisecom_path_mismatch_underlay_expected_overlay"
        if not break_point:
            break_point = "fib_wrong_table_or_dev"
        summary = (
            f"配置意图为 SD-WAN overlay（生效组 {eff_group}），"
            f"实然为 Underlay 出口（{l3.egress_dev or 'main'}）。"
        )
    elif config_intent == "internet_underlay" and observed == "overlay":
        outcome = "mismatch"
        primary = "raisecom_path_mismatch_overlay_on_internet_intent"
        break_point = break_point or "mangle_miss_or_wrong_mark"
        summary = "未列入 url-group 但运行面表现为 Overlay，疑似误加速或它组策略残留。"

    reconcile = PathReconcileResult(
        outcome=outcome,
        primary_rule_case=primary,
        break_point=break_point,
        summary_for_delivery=summary,
    )
    return steps, reconcile, config_intent, observed
