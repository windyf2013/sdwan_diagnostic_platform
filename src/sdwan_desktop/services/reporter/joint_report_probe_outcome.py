"""业务联合报告页首：探测目标 / 方法 / 结果 / 主因结论 / 已排除 / 待核对。

**设计约束（与 `topology_joint_presentation`、`failure_beyond_sdwan_edge_likely`、
`_annotate_problem_nodes`、`build_joint_primary_narrative` 同源）：**

- 页首 ``primary_fault`` 是**单一主因标签**，不再用「；」拼接多个并列标签；
- 当 ``business_fault_beyond_tunnel_edge=True``（即拓扑未将 CPE/Hub 标红、报文已离开 CPE 邻域）时，
  CPE-003 / CPE-004 等**静态启发式**告警**不得**进入 ``primary_fault``，仅作为 ``secondary_findings``
  「待核对项」呈现，避免「报文已出站 + 主因写 CPE/NAT 异常」的逻辑矛盾；
- ``primary_narrative`` 由 :func:`joint_commercial_delivery.build_joint_primary_narrative` 生成，
  与商用交付摘要 ``headline`` **逐字一致**，杜绝两套口径；
- ``ruled_out`` 列出经证据确认的弱否定项（DNS 正常 / 隧道 peer ICMP 正常 / conntrack 见会话等），
  使运维读者在 30 秒内能复述「故障 + 已排除范围」。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity
from sdwan_desktop.services.reporter.joint_commercial_delivery import (
    JointDatapathEvidence,
    _business_probe_rows_all_ok,
    _collect_tunnel_peer_ping_rows,
    build_joint_primary_narrative,
    joint_datapath_evidence_from_targeted_probe,
)

_TRACE_ID_RE = re.compile(r"\s*\(trace_id:\s*[^)]+\)", re.IGNORECASE)
_TOOL_ERR_RE = re.compile(r"^\[[A-Z_]+\]\s*")


def _biz_rows(targeted_probe: Optional[dict]) -> list[dict]:
    """从 ``targeted_probe.data.business_probes`` 取声明业务探测行。"""
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return []
    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return []
    rows = data.get("business_probes")
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _sanitize_probe_detail(text: str) -> str:
    """页首探测结果用：去掉 trace_id 与工具错误码前缀，细节保留在证据链。"""
    if not text:
        return ""
    out = _TRACE_ID_RE.sub("", str(text)).strip()
    out = _TOOL_ERR_RE.sub("", out).strip()
    return out


def _row_probe_methods(row: dict, *, traceroute_enabled: bool = True) -> List[str]:
    """单行业务探测覆盖的探测方法（DNS / TCP / ICMP traceroute）。"""
    methods: List[str] = ["DNS A 解析"]
    if row.get("tcp"):
        methods.append("TCP 端口探测 (tcping)")
    if traceroute_enabled and row.get("trace"):
        methods.append("ICMP Traceroute（路径旁证，不等价 TCP 可达）")
    return methods


def _summarize_row(row: dict) -> dict[str, str]:
    """将单条业务探测行折叠成 ``target/dns/tcp/trace`` 摘要（页首与折叠区共用）。"""
    domain = str(row.get("domain") or "")
    port = row.get("port")
    target = f"{domain}:{port}" if port else domain
    dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
    dns_st = str(dns.get("status") or "—")
    dns_ips = ""
    dd = dns.get("data") if isinstance(dns.get("data"), dict) else {}
    if dd.get("resolved_ips"):
        dns_ips = ", ".join(str(x) for x in dd["resolved_ips"][:6])

    tcp_parts: List[str] = []
    tcp_ok = True
    for t in row.get("tcp") or []:
        if not isinstance(t, dict):
            continue
        host = t.get("host")
        tp = t.get("port")
        st = str(t.get("status") or "—")
        td = t.get("data") if isinstance(t.get("data"), dict) else {}
        port_open = td.get("port_open")
        # tcping 可能返回 status=ok 但 port_open=false（RST/拒绝）；与 ``_infer_business_failure_stage`` /
        # ``_business_probe_rows_all_ok`` 口径一致，须计入失败，避免页首写「探测通过」与主因/折叠区矛盾。
        if st != "ok" or port_open is False:
            tcp_ok = False
        err = _sanitize_probe_detail(str(t.get("error") or "")) if st != "ok" else ""
        line = f"{host}:{tp} {st}"
        if st == "ok" and port_open is False:
            line += "（端口未开放/被拒绝）"
        if err:
            line += f"（{err}）"
        tcp_parts.append(line)
    tcp_st = "ok" if tcp_parts and tcp_ok else ("fail" if tcp_parts else "—")

    trace_parts: List[str] = []
    trace_ok = True
    for tr in row.get("trace") or []:
        if not isinstance(tr, dict):
            continue
        host = tr.get("host") or ""
        st = str(tr.get("status") or "—")
        if st != "ok":
            trace_ok = False
        td = tr.get("data") if isinstance(tr.get("data"), dict) else {}
        summ = td.get("summary") if isinstance(td.get("summary"), dict) else {}
        reached = summ.get("target_reached")
        hops = summ.get("total_hops")
        line = f"{host} {st}"
        if hops is not None:
            line += f" · {hops} 跳"
        if reached is False:
            line += " · 未标示到达目标"
        trace_parts.append(line)
    trace_st = "ok" if trace_parts and trace_ok else ("partial" if trace_parts else "—")

    overall = "ok"
    if dns_st not in ("ok",):
        overall = "fail"
    elif tcp_st == "fail":
        overall = "fail"
    elif trace_st == "partial" and overall == "ok":
        overall = "partial"

    return {
        "target": target,
        "dns_status": dns_st,
        "dns_ips": dns_ips,
        "tcp_status": tcp_st,
        "tcp_detail": "; ".join(tcp_parts) if tcp_parts else "—",
        "trace_status": trace_st,
        "trace_detail": "; ".join(trace_parts[:3]) if trace_parts else "—",
        "overall": overall,
    }


def _phenomenon_line(rows: Sequence[dict]) -> str:
    """根据 DNS/TCP/trace 阶段生成「现象」一句话，供页首主因区使用。

    优先级与 ``_infer_business_failure_stage`` 一致：DNS → TCP → server_port → traceroute → ok。
    """
    if not rows:
        return "未采集到声明业务探测行。"
    parts: List[str] = []
    for row in rows:
        s = _summarize_row(row)
        target = s["target"] or "声明目标"
        if s["dns_status"] != "ok":
            parts.append(f"{target} 域名解析未通过（{s['dns_status']}）")
            continue
        if s["tcp_status"] == "fail":
            tcp_dt = s["tcp_detail"]
            if "端口未开放" in tcp_dt or "被拒绝" in tcp_dt:
                parts.append(f"{target} TCP 已到达目的地址但端口未开放或被拒绝（{tcp_dt}）")
            else:
                parts.append(f"{target} TCP 建连失败（{tcp_dt}）")
            continue
        if s["tcp_status"] == "—" and s["trace_status"] == "partial":
            parts.append(f"{target} DNS 正常；路径追踪未到达目标（旁证）")
            continue
        parts.append(f"{target} 探测通过")
    return "；".join(parts[:3])


def _phenomenon_ok_line(rows: Sequence[dict], *, result_line: str) -> str:
    """本机 DNS/TCP 均成功时页首「探测现象」固定句式（与折叠区 overall 一致）。"""
    if not rows:
        return result_line or "声明目标 DNS/TCP 探测通过"
    targets = [_summarize_row(r)["target"] for r in rows if r.get("domain")]
    tail = "、".join(targets[:4]) if targets else "声明目标"
    return f"{tail}：本机 DNS/TCP 探测通过（与下方「整体探测结果」一致）。"


# ---------------------------------------------------------------------------
# 主因与待核对分层
# ---------------------------------------------------------------------------

# 当 ``beyond_tunnel_edge=True``（已出 CPE 邻域、对端以远）时，下列 cause_id 不得作为页首主因，
# 仅作为 secondary_findings 「待核对项」。与 _annotate_problem_nodes 的 suppress_heuristic 同源。
_HEURISTIC_CONFIG_CAUSE_IDS: frozenset[str] = frozenset({"CPE-003", "CPE-004"})


def _primary_label_for_cause(
    cause_id: str,
    *,
    failure_stage: str,
    beyond_tunnel_edge: bool,
) -> Optional[str]:
    """将根因 ID 映射为「页首主因」标签；不允许进入主因的返回 ``None``。"""
    cid = cause_id or ""
    if cid == "CPE-001":
        return "CPE 不可达"
    if cid == "RAISECOM-LINK-PROT-001":
        return "CPE 链路异常"
    if cid.startswith("CPE-002") or cid.startswith("OVERLAY-"):
        # beyond_tunnel 时已由拓扑/annotate 抑制 OVERLAY 标红；此处不再作为主因。
        if beyond_tunnel_edge:
            return None
        return "SD-WAN 隧道/Overlay 异常"
    if cid in _HEURISTIC_CONFIG_CAUSE_IDS:
        # 配置静态比对类启发式：永不作为页首主因，由 secondary_findings 呈现。
        return None
    if cid.startswith("BIZ-DNS"):
        return "DNS 解析失败"
    if cid.startswith("BIZ-TCP"):
        if failure_stage == "dns":
            return "DNS 解析失败"
        if failure_stage == "server_port":
            return "服务器端口不可达"
        if beyond_tunnel_edge:
            return "公网/对端路径不可达"
        return "服务器不可达"
    return None


def _cause_priority(cause: RootCause) -> int:
    """根因排序权重：CRITICAL > ERROR > WARNING；同级内 CPE-001 / BIZ-* 优先。"""
    sev = cause.severity
    base = 50
    if sev == Severity.CRITICAL:
        base = 0
    elif sev == Severity.ERROR:
        base = 10
    elif sev == Severity.WARNING:
        base = 30
    cid = cause.cause_id or ""
    if cid == "CPE-001":
        return base
    if cid.startswith("BIZ-"):
        return base + 1
    if cid in _HEURISTIC_CONFIG_CAUSE_IDS:
        return base + 20
    return base + 5


def _primary_fault_label(
    causes: Sequence[RootCause],
    *,
    failure_stage: str,
    beyond_tunnel_edge: bool,
) -> str:
    """返回**单一**主因标签字符串；找不到时按 failure_stage / beyond_tunnel_edge 兜底。

    严格不并列：哪怕根因列表里既有 BIZ-TCP 又有 CPE-003，也只输出对端路径类主因；
    CPE-003/004 在已出站场景一律由 secondary_findings 承接。
    """
    for c in sorted(causes, key=_cause_priority):
        label = _primary_label_for_cause(
            c.cause_id,
            failure_stage=failure_stage,
            beyond_tunnel_edge=beyond_tunnel_edge,
        )
        if label:
            return label
    if failure_stage == "dns":
        return "DNS 解析失败"
    if failure_stage == "server_port":
        return "服务器端口不可达"
    if failure_stage == "tcp_connect":
        return "公网/对端路径不可达" if beyond_tunnel_edge else "服务器不可达"
    return ""


# 启发式根因 → 「待核对项」展示文案（避免误读为已确认的 NAT/策略故障）。
_HEURISTIC_FINDING_TEMPLATE: Dict[str, Dict[str, str]] = {
    "CPE-003": {
        "label": "策略源前缀静态未命中（待核对）",
        "note": (
            "PC 快照主地址与 SD-WAN 策略 source 前缀做了静态比对，未必反映真实出站源。"
            "请结合 nf_conntrack 中本流的 src 与上游 NAT 视图核对，不要等同于「策略未生效」。"
        ),
    },
    "CPE-004": {
        "label": "NAT inside 网段静态未覆盖（待核对）",
        "note": (
            "PC 快照主地址与 CPE NAT inside 规则做了静态比对。若路径上存在上游 NAT/三层网关改写源，"
            "CPE 视角看不到 PC 私网源属常见情况；不得仅凭此判定 NAT 失效。"
        ),
    },
    "CPE-002-WARN": {
        "label": "Overlay 计数/状态告警（待核对）",
        "note": "Overlay 启发式告警；在隧道 peer ICMP 正常或已出站场景下，应以会话与对端实证为准。",
    },
}


def _secondary_findings(
    causes: Sequence[RootCause],
    *,
    primary_fault: str,
    beyond_tunnel_edge: bool,
) -> List[Dict[str, str]]:
    """从根因列表生成「待核对」项；不重复 primary_fault 已表达的故障。"""
    out: List[Dict[str, str]] = []
    seen: set[str] = set()
    for c in sorted(causes, key=_cause_priority):
        cid = c.cause_id or ""
        if cid in seen:
            continue
        seen.add(cid)
        tmpl = _HEURISTIC_FINDING_TEMPLATE.get(cid)
        if tmpl is None:
            # 仅 WARNING/INFO 级别的非主因根因，且未被映射到主因标签时，作为「其它待核对」简单透传。
            if c.severity not in (Severity.WARNING, Severity.INFO):
                continue
            mapped = _primary_label_for_cause(
                cid,
                failure_stage="",
                beyond_tunnel_edge=beyond_tunnel_edge,
            )
            if mapped and mapped == primary_fault:
                continue
            out.append(
                {
                    "id": cid or "—",
                    "label": (c.title or cid or "待核对项")[:80],
                    "note": (c.description or "").strip()[:160] or "见根因卡片正文",
                }
            )
            continue
        out.append({"id": cid, "label": tmpl["label"], "note": tmpl["note"]})
    return out[:6]


def _ruled_out_bullets(
    *,
    rows: Sequence[dict],
    evidence: Optional[JointDatapathEvidence],
    beyond_tunnel_edge: bool,
) -> List[str]:
    """生成「已排除（弱否定）」要点：仅写有证据的项，避免空话。"""
    out: List[str] = []
    # DNS：任一目标 DNS 成功就算已排除「域名解析失败」。
    if any((_summarize_row(r).get("dns_status") == "ok") for r in rows):
        out.append("DNS 域名解析正常")
    # 隧道对端 ICMP：全部 peer 通。
    if evidence and evidence.tunnel_probe_row_count > 0 and evidence.tunnel_peers_all_icmp_ok:
        out.append("隧道对端 ICMP 探针均正常（Underlay/隧道未见整段中断）")
    # CPE 上对业务目的 IP 有 conntrack 命中：流量已到达 CPE 邻域（≠ 完全未出 CPE）。
    if evidence and evidence.conntrack_line_count > 0:
        out.append("CPE 上可见发往业务目的的 nf_conntrack 会话条目")
    # 已出 CPE 邻域：明确不应单独归因 CPE。
    if beyond_tunnel_edge:
        out.append("路径旁证显示报文已离开 CPE 邻域（不宜单独判定为 CPE 断点）")
    return out[:5]


# ---------------------------------------------------------------------------
# 公共入口
# ---------------------------------------------------------------------------


def build_joint_report_probe_outcome(
    *,
    biz_targets: List[str],
    targeted_probe: Optional[dict],
    diagnosis: DiagnosisResult,
    joint_failure_driven: bool,
    business_failure_stage: Optional[dict] = None,
    business_fault_beyond_tunnel_edge: bool = False,
) -> Dict[str, Any]:
    """生成业务联合报告页首结论块。

    Args:
        biz_targets: 声明业务目标（``host[:port]`` 列表，可空，将从 ``targeted_probe`` 自动补齐）。
        targeted_probe: 拓扑后主动探测信封（含 ``business_probes`` / ``raw_outputs``）。
        diagnosis: 根因引擎结果（``root_causes`` 用于主因/待核对分层）。
        joint_failure_driven: 是否处于「联合 + 业务探测失败驱动」分支（影响 ``overall`` 兜底）。
        business_failure_stage: ``business_diagnose._infer_business_failure_stage`` 结果。
        business_fault_beyond_tunnel_edge: 与 :func:`topology_joint_presentation.resolve_joint_topology_presentation`
            以及 :func:`_annotate_problem_nodes` 共享的「已出 CPE 邻域 / 对端以远」布尔；
            ``True`` 时启发式 CPE-003/004 不会进入 ``primary_fault``。

    Returns:
        写入 ``topology.report_joint_probe_outcome`` 的字典（联合场景由 ``deep_dive_joint_ux.html`` 渲染，纯深度诊断仍用 ``deep_dive.html``）。
        关键字段：

        - ``primary_fault``：单一主因（字符串，可能为空）；
        - ``primary_narrative``：主叙述段落（与商用交付 ``headline`` 同源）；
        - ``ruled_out``：已排除项列表；
        - ``secondary_findings``：待核对项列表（id/label/note）；
        - ``phenomenon``：现象一句话（DNS/TCP 失败摘要）；
        - 兼容字段：``fault_summary = primary_fault``、``fault_causes = [primary_fault]``。
    """
    rows = _biz_rows(targeted_probe)
    targets = list(biz_targets) or [
        _summarize_row(r)["target"] for r in rows if r.get("domain")
    ]
    methods_union: List[str] = []
    for r in rows:
        for m in _row_probe_methods(r):
            if m not in methods_union:
                methods_union.append(m)
    if not methods_union:
        methods_union = ["DNS A 解析", "TCP 端口探测 (tcping)", "ICMP Traceroute（可选）"]

    row_summaries = [_summarize_row(r) for r in rows]
    any_fail = any(x["overall"] == "fail" for x in row_summaries)
    any_partial = any(x["overall"] == "partial" for x in row_summaries)

    stage_info = business_failure_stage if isinstance(business_failure_stage, dict) else {}
    failure_stage = str(stage_info.get("stage") or "unknown")
    beyond_tunnel_edge = bool(business_fault_beyond_tunnel_edge)

    # overall 与 result_line：保留现网口径；result_line 在页首会被 phenomenon 复盖呈现，但保留供折叠区展示。
    if not rows:
        overall = "unknown"
        result_line = "未采集到业务探测行"
    elif any_fail or joint_failure_driven:
        overall = "fail"
        result_line = "声明目标业务探测未通过（DNS 和/或 TCP 失败）"
    elif any_partial:
        overall = "partial"
        result_line = "DNS/TCP 已通过；Traceroute 未标示到达目标（路径旁证）"
    else:
        overall = "ok"
        result_line = "声明目标 DNS/TCP 探测通过"

    # 主因：单一标签；beyond_tunnel 时 CPE-003/004 自动被 _primary_label_for_cause 滤除。
    causes = list(diagnosis.root_causes or [])
    primary_fault = ""
    if overall in ("fail", "partial") or joint_failure_driven:
        primary_fault = _primary_fault_label(
            causes,
            failure_stage=failure_stage,
            beyond_tunnel_edge=beyond_tunnel_edge,
        )

    # 主叙述：与商用交付摘要 headline 同源（build_joint_primary_narrative）。
    evidence = joint_datapath_evidence_from_targeted_probe(targeted_probe)
    tunnel_rows: List[Dict[str, Any]] = []
    conntrack_lines = 0
    has_syn_only = False
    if evidence is not None:
        conntrack_lines = evidence.conntrack_line_count
        has_syn_only = evidence.conntrack_syn_only_no_established
        # 从原始 raw_outputs 拆出 tunnel rows 形态（供叙述选择）。
        raw = (
            (targeted_probe or {}).get("data", {}).get("raw_outputs")
            if isinstance(targeted_probe, dict)
            else {}
        )
        if isinstance(raw, dict):
            tunnel_rows = _collect_tunnel_peer_ping_rows(raw)
    biz_all_ok = _business_probe_rows_all_ok(
        (targeted_probe or {}).get("data", {}).get("business_probes")
        if isinstance(targeted_probe, dict)
        else None
    )
    primary_narrative, _ = build_joint_primary_narrative(
        tunnel_rows=tunnel_rows,
        conntrack_lines=conntrack_lines,
        has_syn_only=has_syn_only,
        cause_ids={c.cause_id for c in causes},
        biz_all_ok=biz_all_ok,
        underlay_declared_business_focus=False,
    )

    ruled_out = _ruled_out_bullets(
        rows=rows,
        evidence=evidence,
        beyond_tunnel_edge=beyond_tunnel_edge,
    )
    secondary_findings = _secondary_findings(
        causes,
        primary_fault=primary_fault,
        beyond_tunnel_edge=beyond_tunnel_edge,
    )

    # 页首「探测现象」：失败/部分失败用逐行摘要；成功必须与 overall=ok 对齐，避免与主因区矛盾。
    if overall == "ok":
        phenomenon = _phenomenon_ok_line(rows, result_line=result_line)
    elif overall == "partial":
        phenomenon = _phenomenon_line(rows) or result_line
    else:
        phenomenon = _phenomenon_line(rows)
        if not phenomenon:
            phenomenon = result_line

    # 兼容字段：fault_summary / fault_causes 保留供旧模板与 JSON 消费者，但仅放主因（不再分号拼接）。
    fault_summary = primary_fault if primary_fault else (
        "请查看根因分析与证据链" if overall == "fail" else ""
    )
    fault_causes = [primary_fault] if primary_fault else []

    return {
        "targets": targets,
        "targets_line": "、".join(targets) if targets else "—",
        "methods": methods_union,
        "methods_line": "；".join(methods_union),
        "results": row_summaries,
        "overall": overall,
        "result_line": result_line,
        "phenomenon": phenomenon,
        "primary_fault": primary_fault,
        "primary_narrative": primary_narrative,
        "ruled_out": ruled_out,
        "secondary_findings": secondary_findings,
        "fault_causes": fault_causes,
        "fault_summary": fault_summary,
    }
