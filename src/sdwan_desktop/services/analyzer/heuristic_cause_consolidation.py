"""配置类启发式根因综合：禁止多卡片/多段旁证堆叠，输出唯一可复述结论。

business-diagnose 联合场景：CPE-003 / CPE-004 / CPE-002-WARN 等经本模块合并为
``CPE-CONFIG-HEURISTIC`` 单条 WARNING；会话与路径旁证仅写入一段综合叙述。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from sdwan_desktop.core.types.diagnosis import RootCause, Severity
from sdwan_desktop.services.reporter.joint_commercial_delivery import (
    joint_datapath_evidence_from_targeted_probe,
    path_beyond_tunnel_likely,
)

logger = logging.getLogger(__name__)

# 合并前源 ID（检测器产出）
CONFIG_HEURISTIC_SOURCE_IDS: frozenset[str] = frozenset(
    {"CPE-003", "CPE-004", "CPE-002-WARN"}
)
# 合并后对外 ID（报告 / 页首待核对）
CONSOLIDATED_CONFIG_HEURISTIC_ID = "CPE-CONFIG-HEURISTIC"


def _business_joint_probe_context(targeted_probe: Optional[Dict[str, Any]]) -> bool:
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return False
    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return False
    rows = data.get("business_probes")
    return isinstance(rows, list) and len(rows) > 0


@dataclass
class HeuristicConsolidationContext:
    """综合模块输入：各检测器结论 + 运行面旁证（不堆叠原文）。"""

    policy_mismatch: bool = False
    nat_mismatch: bool = False
    overlay_warn: bool = False
    business_probes_all_ok: bool = False
    path_beyond_tunnel: bool = False
    tunnel_icmp_ok_with_conntrack: bool = False
    overlay_flow_aligned: bool = False
    session_enabled: bool = False
    session_line_count: int = 0
    session_has_established: bool = False
    session_syn_only: bool = False
    session_closing_residual: bool = False
    matched_ips: List[str] = field(default_factory=list)
    source_ids: Set[str] = field(default_factory=set)


def build_heuristic_consolidation_context(
    causes: Sequence[RootCause],
    *,
    targeted_probe: Optional[Dict[str, Any]] = None,
    overlay_policy_flow: Optional[Dict[str, Any]] = None,
    session_evidence: Optional[Dict[str, Any]] = None,
    business_probes_all_ok: bool = False,
) -> HeuristicConsolidationContext:
    """从根因列表与信封旁证构建综合上下文。"""
    ctx = HeuristicConsolidationContext(business_probes_all_ok=business_probes_all_ok)
    for c in causes:
        cid = c.cause_id or ""
        if cid in CONFIG_HEURISTIC_SOURCE_IDS:
            ctx.source_ids.add(cid)
        if cid == "CPE-003":
            ctx.policy_mismatch = True
        elif cid == "CPE-004":
            ctx.nat_mismatch = True
        elif cid == "CPE-002-WARN":
            ctx.overlay_warn = True

    ev = joint_datapath_evidence_from_targeted_probe(targeted_probe)
    if ev is not None:
        ctx.path_beyond_tunnel = path_beyond_tunnel_likely(ev)
        ctx.tunnel_icmp_ok_with_conntrack = (
            ev.tunnel_probe_row_count > 0
            and ev.tunnel_peers_all_icmp_ok
            and ev.conntrack_line_count > 0
        )

    if isinstance(session_evidence, dict) and session_evidence.get("enabled"):
        ctx.session_enabled = True
        ctx.session_line_count = int(session_evidence.get("line_count") or 0)
        ctx.session_has_established = bool(session_evidence.get("has_progress_state"))
        ctx.session_syn_only = bool(session_evidence.get("has_only_syn_or_unreplied"))
        ctx.session_closing_residual = bool(session_evidence.get("has_closing_residual_pattern"))
        ctx.matched_ips = list(session_evidence.get("matched_ips") or [])

    if isinstance(overlay_policy_flow, dict) and overlay_policy_flow.get("status") in (
        "ok",
        "partial",
    ):
        data = overlay_policy_flow.get("data")
        if isinstance(data, dict):
            tags = [str(t).lower() for t in (data.get("scenario_tags") or [])]
            notes = " ".join(str(x) for x in (data.get("probe_evidence_notes") or [])).lower()
            blob = notes + " " + " ".join(tags)
            if any(t in tags for t in ("vxlan", "l2tp", "ipsec")) and any(
                k in blob for k in ("fwmark", "ip rule", "mangle", "ipset", "vxlan", "l2tp", "ipsec")
            ):
                ctx.overlay_flow_aligned = True

    return ctx


def _session_clause(ctx: HeuristicConsolidationContext) -> str:
    if not ctx.session_enabled:
        return ""
    ips = ", ".join(ctx.matched_ips[:4])
    if ctx.session_line_count == 0:
        return (
            f"nf_conntrack 按业务目的地址采样零命中（{ips or '—'}），"
            "不能单独证明策略或 NAT 失效，需结合上游 NAT 与采样时刻。"
        )
    if ctx.session_has_established:
        return (
            f"nf_conntrack 对业务目的地址有已建立会话（{ips}，{ctx.session_line_count} 条），"
            "不宜单独将策略/NAT 静态未命中判为转发面故障。"
        )
    if ctx.session_syn_only:
        return (
            f"nf_conntrack 呈 SYN/UNREPLIED（{ips}，{ctx.session_line_count} 条），"
            "更符合对端或中间路径问题，不宜单独归因 CPE 策略/NAT 配置。"
        )
    if ctx.session_closing_residual:
        return (
            f"nf_conntrack 以收尾态为主（{ips}，{ctx.session_line_count} 条），"
            "多为探测结束残留，不宜单独作为配置根因依据。"
        )
    return (
        f"nf_conntrack 命中 {ctx.session_line_count} 条（{ips}），"
        "须与配置静态比对交叉验证。"
    )


def _synthesize_title_and_body(
    ctx: HeuristicConsolidationContext,
    source_confidences: Sequence[float],
) -> tuple[str, str, float]:
    """返回 (title, description, confidence) 单一结论。"""
    conf = min(source_confidences) if source_confidences else 0.72
    parts: List[str] = []

    if ctx.business_probes_all_ok:
        title = "配置静态核对（声明业务探测已达通，仅作人工复核）"
        parts.append(
            "本机 DNS/TCP 探测已通过；下列为 PC 快照与 CPE 配置面的静态比对，"
            "不等价于转发面抓包结论。"
        )
        conf = min(conf, 0.58)
    elif ctx.path_beyond_tunnel or ctx.tunnel_icmp_ok_with_conntrack:
        title = "配置静态核对（对端/隧道旁证优先，策略与 NAT 仅供参考）"
        parts.append(
            "隧道对端 ICMP 与 nf_conntrack 形态更符合对端或目的路径类问题；"
            "策略源前缀与 NAT inside 仅为配置面对照，不得解读为 CPE 未转发或未走隧道/Overlay。"
        )
        conf = min(conf, 0.62)
    elif ctx.overlay_flow_aligned:
        title = "配置静态核对（Overlay/策略证据链已对账）"
        parts.append(
            "报告已归纳 vxlan/隧道面及 MARK→ip rule→多路由表等组件；"
            "PC 快照与策略/NAT 规则仅为静态比对，须与 conntrack 源及业务接口交叉验证。"
        )
        conf = min(conf, 0.65)
    else:
        title = "配置静态核对（综合结论）"
        hints: List[str] = []
        if ctx.policy_mismatch:
            hints.append("PC 快照主地址未匹配 sdwan_policies.source 前缀")
        if ctx.nat_mismatch:
            hints.append("PC 快照主地址未匹配 NAT inside 规则")
        if ctx.overlay_warn:
            hints.append("Overlay 隧道状态存在告警")
        if hints:
            parts.append("；".join(hints) + "。")
        else:
            parts.append("存在配置面启发式提示，详见证据链。")
        if ctx.policy_mismatch and ctx.nat_mismatch:
            parts.append(
                "SD-WAN 场景下经 Overlay 转发的业务通常不要求 PC 网段编入 CPE NAT inside；"
                "Internet Underlay 出口仍须核对 NAT。"
            )

    session = _session_clause(ctx)
    if session:
        parts.append(session)

    if ctx.session_enabled:
        if ctx.session_line_count == 0:
            conf = min(conf, 0.66)
        elif ctx.session_has_established:
            conf = min(conf, 0.62)
        elif ctx.session_syn_only:
            conf = min(conf, 0.70)
        elif ctx.session_closing_residual:
            conf = min(conf, 0.64)

    body = " ".join(parts).strip()
    return title, body, conf


def consolidate_heuristic_root_causes(
    causes: List[RootCause],
    ctx: HeuristicConsolidationContext,
    *,
    targeted_probe: Optional[Dict[str, Any]] = None,
    topology_pc_node_id: str = "",
    topology_cpe_node_id: str = "",
) -> List[RootCause]:
    """合并配置启发式为单条 ``CPE-CONFIG-HEURISTIC``；非 business-diagnose 且仅一条源时保持原样。"""
    if not ctx.source_ids:
        return causes

    if not _business_joint_probe_context(targeted_probe):
        return causes

    non_heuristic = [c for c in causes if (c.cause_id or "") not in CONFIG_HEURISTIC_SOURCE_IDS]
    source_conf = [float(c.confidence or 0.8) for c in causes if (c.cause_id or "") in CONFIG_HEURISTIC_SOURCE_IDS]
    title, description, confidence = _synthesize_title_and_body(ctx, source_conf)
    refs: List[str] = []
    if topology_pc_node_id:
        refs.append(topology_pc_node_id)
    if topology_cpe_node_id:
        refs.append(topology_cpe_node_id)

    consolidated = RootCause(
        cause_id=CONSOLIDATED_CONFIG_HEURISTIC_ID,
        title=title,
        description=description,
        severity=Severity.WARNING,
        confidence=confidence,
        evidence_refs=refs,
        matched_rules=["CONFIG-HEURISTIC-CONSOLIDATED"],
    )
    logger.info(
        "启发式根因已综合为 %s（源: %s）",
        CONSOLIDATED_CONFIG_HEURISTIC_ID,
        ",".join(sorted(ctx.source_ids)),
    )
    return non_heuristic + [consolidated]
