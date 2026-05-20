"""业务联合报告：首屏人类可读结论与「如何阅读」指引。

与 ``joint_report_probe_outcome`` 分工：页首仅渲染一份「核查结论」；
``probe_outcome`` 的明细（DNS/TCP 逐目标、已排除、待核对）收入同区块内折叠，不另起 hero。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity

_MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _strip_md_bold(text: str) -> str:
    return _MD_BOLD_RE.sub(r"\1", str(text or "").strip())


def _targets_line(probe_outcome: Dict[str, Any], topology_dict: Dict[str, Any]) -> str:
    line = str(probe_outcome.get("targets_line") or "").strip()
    if line and line != "—":
        return line
    return str(topology_dict.get("report_html_business_targets_line") or "声明业务目标").strip()


def _presentation(topology_dict: Dict[str, Any]) -> Dict[str, Any]:
    raw = topology_dict.get("topology_joint_presentation")
    return raw if isinstance(raw, dict) else {}


def _path_summary_short(
    *,
    show_overlay: bool,
    evidence_tier: str,
    egress_shape: str,
    url_group_supplement: str,
    datapath_banner: str,
) -> str:
    """页首路径一句（禁止整段技术 banner）。"""
    ug = _strip_md_bold(url_group_supplement).strip()
    ug_short = ""
    if "url-group" in ug or "url group" in ug.lower():
        m = re.search(r"url-?group[「\"]?([^」\"]+)[」\"]?", ug, re.I)
        grp = m.group(1).strip() if m else ""
        if grp:
            ug_short = f"，命中业务域 {grp}"

    if show_overlay:
        if evidence_tier == "precise":
            base = "CPE 会话与路由旁证显示：业务流经 SD-WAN 隧道（Overlay）转发"
        else:
            base = "旁证提示业务流可能经 SD-WAN 隧道（Overlay），详见证据链"
        if egress_shape == "early_public":
            base += "；出 CPE 后较早进入公网路径"
        elif egress_shape == "wan_gateway":
            base += "；经 WAN 网关再入公网"
        return base + ug_short + "。"

    if egress_shape == "early_public":
        return (
            "本轮未见需绑定的隧道示意：离开 CPE 后走公网 Underlay（早期公网跳）"
            + ug_short
            + "。"
        )
    if egress_shape == "wan_gateway":
        return "本轮未见需绑定的隧道示意：经 WAN 网关出网（Underlay）" + ug_short + "。"

    if datapath_banner and "未表现为经本设备转发" in datapath_banner:
        return "CPE 侧未采样到与声明目的相关的会话。"

    return "路径以 Underlay 公网形态为主；隧道示意未展示（证据不足或产品门控）" + ug_short + "。"


def _count_root_cause_buckets(causes: Sequence[RootCause]) -> Dict[str, int]:
    hard = 0
    heuristic = 0
    for c in causes:
        if c.severity in (Severity.CRITICAL, Severity.ERROR):
            hard += 1
        elif c.severity == Severity.WARNING:
            heuristic += 1
    return {"hard": hard, "heuristic": heuristic, "total": len(causes)}


def build_joint_report_reading_layer(
    *,
    probe_outcome: Dict[str, Any],
    topology_dict: Dict[str, Any],
    diagnosis: DiagnosisResult,
    joint_failure_driven: bool,
) -> Dict[str, Any]:
    """生成写入 ``topology.report_joint_reading_layer`` 的首屏阅读层。"""
    po = probe_outcome if isinstance(probe_outcome, dict) else {}
    pres = _presentation(topology_dict)
    causes = list(diagnosis.root_causes or [])
    buckets = _count_root_cause_buckets(causes)

    overall = str(po.get("overall") or "unknown")
    primary_fault = str(po.get("primary_fault") or "").strip()
    targets = _targets_line(po, topology_dict)

    show_overlay = bool(pres.get("show_business_flow_overlay") or pres.get("show_overlay_tunnel_strip"))
    evidence_tier = str(pres.get("evidence_tier") or "underlay_only")
    egress_shape = str(pres.get("egress_shape") or "")
    biz_probe_ok = bool(pres.get("business_probe_all_ok"))

    gate_banner = str(topology_dict.get("declared_business_datapath_banner") or "")
    jpe = topology_dict.get("joint_path_evidence")
    url_sup = ""
    if isinstance(jpe, dict):
        url_sup = str(jpe.get("url_group_supplement") or "")

    path_short = _path_summary_short(
        show_overlay=show_overlay,
        evidence_tier=evidence_tier,
        egress_shape=egress_shape,
        url_group_supplement=url_sup,
        datapath_banner=gate_banner,
    )
    path_detail = _strip_md_bold(gate_banner) or path_short

    if overall == "fail" or joint_failure_driven:
        verdict_label = "探测未通过"
        verdict_tone = "error"
        headline = f"{targets}：本机 DNS/TCP 探测未通过。"
    elif overall == "partial":
        verdict_label = "路径旁证不全"
        verdict_tone = "warning"
        headline = f"{targets}：本机 DNS/TCP 已通过；路径旁证不完整。"
    elif primary_fault:
        verdict_label = "存在告警项"
        verdict_tone = "warning" if buckets["hard"] == 0 else "error"
        headline = f"{targets}：{primary_fault}。"
    elif buckets["hard"] > 0:
        verdict_label = "存在告警项"
        verdict_tone = "error"
        headline = f"{targets}：规则引擎输出 {buckets['hard']} 项严重/错误级结论。"
    elif biz_probe_ok and buckets["heuristic"] > 0:
        verdict_label = "探测通过"
        verdict_tone = "success"
        headline = (
            f"{targets}：本机 DNS/TCP 探测通过；CPE 侧可见相关会话。"
            f"另有 {buckets['heuristic']} 条配置静态比对待核对（见「配置核对」）。"
        )
    elif biz_probe_ok:
        verdict_label = "探测通过"
        verdict_tone = "success"
        headline = f"{targets}：本机 DNS/TCP 探测通过；CPE 侧采样与拓扑一致。"
    else:
        verdict_label = "核查完成"
        verdict_tone = "info"
        headline = f"{targets}：联合核查已完成。"

    if overall == "ok" and biz_probe_ok:
        probe_bullet = f"{targets}：本机 DNS/TCP 探测通过。"
    else:
        probe_bullet = str(
            po.get("phenomenon") or po.get("result_line") or "见下方探测明细。"
        )[:220]

    takeaway_bullets: List[Dict[str, str]] = [
        {"key": "本机", "text": probe_bullet},
        {"key": "路径", "text": path_short[:220]},
    ]
    if primary_fault:
        takeaway_bullets.append({"key": "主故障", "text": primary_fault[:220]})

    root_causes_heuristic_only = (
        biz_probe_ok
        and overall == "ok"
        and not primary_fault
        and buckets["hard"] == 0
        and buckets["heuristic"] > 0
    )
    root_causes_nav_label = (
        f"配置核对 ({buckets['heuristic']})"
        if root_causes_heuristic_only
        else (f"根因分析 ({buckets['total']})" if buckets["total"] else "根因分析")
    )

    reading_steps = [
        {
            "title": "① 核查结论",
            "text": "本机探测结果、路径判断与综合置信度。",
            "anchor": "#report-joint-outcome",
        },
        {
            "title": "② 网络拓扑",
            "text": "PC→CPE→公网或隧道示意；链路表在拓扑内折叠。",
            "anchor": "#topology",
        },
        {
            "title": "③ 交付摘要",
            "text": "T0–T3 一行式核对清单。",
            "anchor": "#delivery",
        },
        {
            "title": "④ 配置核对" if root_causes_heuristic_only else "④ 根因分析",
            "text": (
                "静态策略/NAT 比对条目（启发式，非转发面定论）。"
                if root_causes_heuristic_only
                else "规则引擎结论与置信度。"
            ),
            "anchor": "#root-causes",
        },
        {
            "title": "⑤ 证据链",
            "text": "conntrack、FIB、策略节选与原始命令输出。",
            "anchor": "#evidence-chain",
        },
    ]

    audience_hints = [
        {
            "role": "网络工程师",
            "focus": "核查结论 → 拓扑 → 证据链；有配置核对章节时对照 conntrack 源 IP",
        },
        {
            "role": "交付 / 留档",
            "focus": "核查结论 + 交付摘要 + 页眉 Trace ID",
        },
    ]

    return {
        "verdict_label": verdict_label,
        "verdict_tone": verdict_tone,
        "headline": headline,
        "takeaway_bullets": takeaway_bullets,
        "path_summary_short": path_short,
        "path_detail": path_detail[:1200],
        "reading_steps": reading_steps,
        "audience_hints": audience_hints,
        "root_causes_heuristic_only": root_causes_heuristic_only,
        "root_causes_nav_label": root_causes_nav_label,
        "root_causes_section_title": (
            "配置核对（启发式 · 非故障）"
            if root_causes_heuristic_only
            else "根因分析"
        ),
        "root_causes_badge_text": (
            f"{buckets['heuristic']} 条待核对"
            if root_causes_heuristic_only
            else (f"{buckets['total']} 个问题" if buckets["total"] else "")
        ),
    }
