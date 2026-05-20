"""联合业务诊断 HTML 的「商用交付摘要」载荷构建。

将 ``targeted_probe`` 原始输出（nf_conntrack、ipset、隧道 peer ping）与根因列表
合成为面向用户/运维的阅读层，**不替代**根因引擎结论，仅做呈现层归纳与消歧。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sdwan_desktop.services.diagnosis.business_trace_evidence import (
    BusinessTraceEvidence,
    analyze_business_trace_evidence,
)
from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    targeted_probe_has_business_target_conntrack_hits,
)

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause


def _pc_primary_ip_from_topology(topology_dict: Dict[str, Any]) -> Optional[str]:
    pc_id = topology_dict.get("pc_node_id")
    if not pc_id:
        return None
    for n in topology_dict.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        if n.get("id") == pc_id and n.get("type") == "pc":
            ip = (n.get("ip_address") or "").strip()
            return ip or None
    return None


def _first_conntrack_src_ip(raw: str) -> Optional[str]:
    if not raw or not str(raw).strip():
        return None
    m = re.search(r"\bsrc=(\d+\.\d+\.\d+\.\d+)\b", str(raw))
    return m.group(1) if m else None


def _conntrack_blob_has_src_ipv4(ct_blob: str, ipv4: str) -> bool:
    """nf_conntrack 采样文本中是否出现以该 IPv4 为四层源（src=）的条目。"""
    if not (ct_blob or "").strip() or not (ipv4 or "").strip():
        return False
    return bool(re.search(rf"\bsrc={re.escape(str(ipv4).strip())}\b", str(ct_blob)))


def _conntrack_line_count(raw: str) -> int:
    return sum(1 for line in (raw or "").splitlines() if line.strip() and not line.strip().startswith("#"))


def _summarize_ping_output(raw: str) -> tuple[str, str]:
    """返回 (ok|fail|partial|unknown, 单行摘要)。"""
    text = (raw or "").lower()
    if not (raw or "").strip():
        return "unknown", "无输出（命令可能未执行或超时）。"
    for line in (raw or "").splitlines():
        ls = line.strip()
        if "packets transmitted" in ls.lower() and "received" in ls.lower():
            if "100% packet loss" in ls or ("0 received" in ls and "transmitted" in ls):
                return "fail", ls
            if "0% packet loss" in ls or " 0.0% packet loss" in ls:
                return "ok", ls
            return "partial", ls
    if "unknown host" in text or "name or service not known" in text:
        return "fail", "解析失败或未知主机（见原始输出）。"
    if "unreachable" in text or "100% packet loss" in text:
        return "fail", "网络不可达或全部丢包（见原始输出）。"
    return "unknown", "已采集 ping 输出，未匹配到标准统计行；请展开原始输出核对。"


def _collect_tunnel_peer_ping_rows(raw_outputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for k, v in sorted((raw_outputs or {}).items()):
        if not str(k).startswith("diagnose:ping tunnel_peer "):
            continue
        ip = str(k).replace("diagnose:ping tunnel_peer ", "").strip()
        status, summary = _summarize_ping_output(str(v or ""))
        rows.append(
            {
                "peer_ip": ip,
                "status": status,
                "summary_line": summary,
                "raw_key": k,
            }
        )
    return rows


def _nf_conntrack_blob_for_biz_ips(raw_outputs: Dict[str, Any], biz_ips: Sequence[str]) -> str:
    parts: List[str] = []
    for ip in biz_ips:
        key = f"diagnose:nf_conntrack grep {ip}"
        if key in (raw_outputs or {}):
            parts.append(str(raw_outputs.get(key) or ""))
    return "\n".join(parts)


def _ipset_cdn_notice(ipset_raw: str, biz_ips: Sequence[str], probe_domain: str) -> Optional[str]:
    if not (ipset_raw or "").strip() or not biz_ips:
        return None
    dom = (probe_domain or "").lower().strip()
    for ip in biz_ips:
        for line in ipset_raw.splitlines():
            if ip not in line or "comment" not in line.lower():
                continue
            cm = re.search(r'comment\s+"([^"]*)"', line)
            if not cm:
                continue
            cmt = cm.group(1).lower()
            if dom and dom not in cmt and ip in line:
                return (
                    f"提示：ipset 中 IP `{ip}` 的注释为「{cm.group(1)}」，与当前探测域名「{probe_domain}」"
                    " 可能不一致；该 IP 可能为 CDN/共享地址，不宜仅凭 ipset 注释绑定业务含义。"
                )
    return None


def _cause_ids(causes: Sequence[RootCause]) -> set[str]:
    return {c.cause_id for c in causes}


def build_joint_primary_narrative(
    *,
    tunnel_rows: Sequence[Dict[str, Any]],
    conntrack_lines: int,
    has_syn_only: bool,
    cause_ids: set[str],
    biz_all_ok: bool = False,
    underlay_declared_business_focus: bool = False,
) -> tuple[str, List[str]]:
    """业务联合报告主叙述（页首与商用交付摘要共用单一事实源）。

    决策顺序：
    1. ``biz_all_ok=True``：本机 DNS+TCP 已通，呈现「可达性基线」叙述；
       ``underlay_declared_business_focus=True`` 时进一步明示「不归因 Overlay/隧道域」。
    2. 任一隧道 peer ICMP 失败：Underlay/隧道可达性存疑，业务 TCP 超时可能为连带现象。
    3. 全部隧道 peer ICMP 通 + conntrack 对业务目的 IP 命中 + SYN-only 形态：
       更符合「隧道对端以远」（公网/对端路径或对端策略），非「隧道完全不通」。
    4. conntrack 对业务目的 IP 命中行数为 0：未观察到声明流出现在 CPE 视图（可能未命中 CPE、
       已过期或上游 NAT 改写源使本机视角看不到 PC src），需结合 PC 路径与策略核对。
    5. 兜底：按核查表与根因卡片对账。

    Returns:
        ``(headline, sub_bullets)``，``sub_bullets`` 用于商用阅读层 ``notices`` 段尾的轻量提示，
        页首叙述只引用 ``headline``。
    """
    bullets: List[str] = []
    all_ping_ok = bool(tunnel_rows) and all(r.get("status") == "ok" for r in tunnel_rows)
    any_ping_fail = any(r.get("status") == "fail" for r in tunnel_rows)

    # 业务探测整体已通：商用阅读层与页首均输出「可达性基线」语；不向用户报告无证据的故障原因。
    if biz_all_ok:
        if underlay_declared_business_focus:
            head = (
                "本机业务探测（DNS/TCP）已成功；以下为 CPE 侧采样与会话形态摘要，"
                "用于核对出口、NAT 及域名解析是否与现网声明目标一致（未将本流量归因于 Overlay/隧道域）。"
            )
        else:
            head = (
                "本机业务探测（DNS/TCP）已成功；以下为 CPE 侧采样与会话形态摘要，"
                "用于核对策略、NAT 与隧道域配置是否与现网业务一致。"
            )
        bullets.append("本段不替代安全/变更评审；若仅做故障排查且本机已通，可将本报告作为「可达性基线」留档。")
        return head, bullets

    if any_ping_fail:
        head = (
            "隧道对端 ICMP 探针未全部成功：Underlay/隧道可达性存疑，"
            "请优先核对 WAN、对端地址与隧道状态后再看业务 TCP。"
        )
        bullets.append("若 ping 失败，业务 TCP 超时可能为连带现象，不宜单独归因到公网目的地址。")
        return head, bullets

    if all_ping_ok and conntrack_lines > 0 and has_syn_only:
        head = (
            "隧道对端网络层可达（ICMP 正常），且 CPE 上可见发往业务目的地址的 TCP 会话，"
            "但长期处于 SYN 未建立完成状态；更可能发生在隧道对端以远、目的侧或对端路径策略，"
            "而非「隧道完全不通」。"
        )
        if cause_ids & {"CPE-003", "CPE-004", "CPE-CONFIG-HEURISTIC"}:
            # 与 _annotate_problem_nodes / topology presentation 的 suppress_heuristic 同源：
            # 已出站痕迹下，配置类启发式仅作「待核对」，不得提升为「设备未转发该流」。
            bullets.append(
                "配置类告警（策略/NAT 未命中）与上述会话并存时：请以 conntrack 源地址与 PC 快照源地址是否一致为准，"
                "避免将「PC 网段未命中静态规则」直接等同于「设备未转发该业务流」。"
            )
        return head, bullets

    if conntrack_lines == 0:
        head = (
            "在采样的 nf_conntrack 过滤结果中未见业务目的 IP 相关会话："
            "可能未命中 CPE、会话已过期、或中间 NAT 导致观察视角不一致；请结合 PC 路径与策略核对。"
        )
        return head, bullets

    head = "请结合下方核查表与根因卡片逐项核对；若证据相互矛盾，以原始命令输出为准并安排复测。"
    return head, bullets


# 历史别名：保留 _pick_primary_narrative 以避免外部 import 中断；新代码请用 build_joint_primary_narrative。
_pick_primary_narrative = build_joint_primary_narrative


def _has_syn_only_conntrack(blob: str) -> bool:
    """CPE 侧 conntrack 是否仅见 TCP 未完成握手形态（不含 ICMP 的 UNREPLIED）。

    ``TIME_WAIT`` / ``ESTABLISHED`` 等视为曾建立或已结束，与 §5.1 对账口径一致。
    """
    if not blob.strip():
        return False
    tcp_lines = [
        ln
        for ln in blob.splitlines()
        if ln.strip()
        and not ln.strip().startswith("#")
        and re.search(r"\btcp\b", ln, re.IGNORECASE)
    ]
    if not tcp_lines:
        return False
    completed = re.compile(
        r"\b(ESTABLISHED|TIME_WAIT|FIN_WAIT|CLOSE_WAIT|CLOSE|DELETE)\b",
        re.IGNORECASE,
    )
    for ln in tcp_lines:
        if completed.search(ln) or re.search(r"\bASSURED\b", ln, re.IGNORECASE):
            return False
    for ln in tcp_lines:
        if re.search(r"\bSYN_SENT\b", ln, re.IGNORECASE) or re.search(
            r"\bSYN_RECV\b", ln, re.IGNORECASE
        ):
            return True
        if "[UNREPLIED]" in ln:
            return True
    return False


@dataclass(frozen=True, slots=True)
class JointDatapathEvidence:
    """隧道 ICMP + conntrack 摘要，供拓扑高亮与商用叙述对齐（避免「对端以远」与 Overlay 红标矛盾）。"""

    tunnel_probe_row_count: int
    tunnel_peers_all_icmp_ok: bool
    tunnel_peers_any_icmp_fail: bool
    conntrack_line_count: int
    conntrack_syn_only_no_established: bool


def joint_datapath_evidence_from_targeted_probe(
    targeted_probe: Optional[Dict[str, Any]],
) -> Optional[JointDatapathEvidence]:
    """从 ``targeted_probe`` 提取路径证据；无信封或缺 data 时返回 ``None``。"""
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return None
    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return None
    raw_outputs: Dict[str, Any] = dict(data.get("raw_outputs") or {})
    biz_ips: List[str] = list(data.get("biz_target_ips") or [])
    rows = data.get("business_probes")
    if not biz_ips and isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
            dd = dns.get("data") if isinstance(dns.get("data"), dict) else {}
            for ip in dd.get("resolved_ips") or []:
                if ip and ip not in biz_ips:
                    biz_ips.append(str(ip))
    tunnel_rows = _collect_tunnel_peer_ping_rows(raw_outputs)
    trc = len(tunnel_rows)
    all_ok = trc > 0 and all(r.get("status") == "ok" for r in tunnel_rows)
    any_fail = any(r.get("status") == "fail" for r in tunnel_rows)
    ct_blob = _nf_conntrack_blob_for_biz_ips(raw_outputs, biz_ips)
    ct_count = _conntrack_line_count(ct_blob)
    syn_only = _has_syn_only_conntrack(ct_blob)
    return JointDatapathEvidence(
        tunnel_probe_row_count=trc,
        tunnel_peers_all_icmp_ok=all_ok,
        tunnel_peers_any_icmp_fail=any_fail,
        conntrack_line_count=ct_count,
        conntrack_syn_only_no_established=syn_only,
    )


def path_beyond_tunnel_likely(ev: JointDatapathEvidence) -> bool:
    """隧道 peer 全通且 CPE 上对业务目的 IP 的会话停留在 SYN/UNREPLIED，更符合「对端以远」而非隧道断。"""
    if ev.tunnel_probe_row_count <= 0 or not ev.tunnel_peers_all_icmp_ok:
        return False
    if ev.conntrack_line_count <= 0:
        return False
    return ev.conntrack_syn_only_no_established


def failure_beyond_sdwan_edge_likely(
    targeted_probe: Optional[Dict[str, Any]],
    joint_ev: Optional[JointDatapathEvidence],
    *,
    cpe_configuration: Optional[Any] = None,
    topology_dict: Optional[Dict[str, Any]] = None,
) -> bool:
    """声明业务 TCP 失败时，故障点是否更符合「已出 SD-WAN/CPE 域」而非 CPE 本机。

    融合：隧道 peer ICMP + conntrack 会话形态 + **PC 侧 traceroute 离开 CPE 邻域**（见 ``business_trace_evidence``）。
    与 ``targeted_probe_has_business_target_conntrack_hits`` 对齐，避免 gate/RCA 已认定 conntrack 命中而本函数仍为假。
    """
    if joint_ev and path_beyond_tunnel_likely(joint_ev):
        return True
    trace_ev: BusinessTraceEvidence = analyze_business_trace_evidence(
        targeted_probe, cpe_configuration, topology_dict
    )
    if not trace_ev.trace_available or not trace_ev.egress_past_cpe:
        return False
    if targeted_probe_has_business_target_conntrack_hits(targeted_probe):
        return True
    if joint_ev and joint_ev.conntrack_line_count > 0:
        return True
    if joint_ev and joint_ev.conntrack_syn_only_no_established:
        return True
    return False


def targeted_probe_business_rows_all_ok(targeted_probe: Optional[Dict[str, Any]]) -> bool:
    """拓扑后信封中的 ``business_probes`` 是否全部 DNS/TCP 成功（与商用交付载荷口径一致）。

    **不包含** ``trace``（ICMP/UDP 路由追踪）：与 TCP 服务可达性不等价，见 ``spec/detail_function_design.md`` §2.2.2。
    """
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return False
    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return False
    return _business_probe_rows_all_ok(data.get("business_probes"))


def business_joint_should_present_overlay_tunnel_narrative(
    targeted_probe: Optional[Dict[str, Any]],
    cpe_configuration: Optional[Any] = None,
    topology_dict: Optional[Dict[str, Any]] = None,
) -> bool:
    """业务路径联合诊断是否应呈现 Overlay/隧道类叙述与证据链步骤。

    **口径**：Raisecom MSG5200B 见 ``compute_joint_overlay_datapath_gate``（D0–D5）；
    其他厂商：仅 traceroute 命中隧道/Overlay 时展示。可选传入 ``cpe_configuration`` 与
    ``topology_dict``（与 ``topology.to_dict()`` 一致）以启用 5200B 分支。

    Returns:
        ``True``：可启用 ``run_overlay_policy_flow_step`` 及模板中 Overlay 证据块。
        ``False``：不将声明流与隧道面在拓扑上绑定呈现。
    """
    from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
        joint_overlay_should_run_policy_flow,
    )

    return joint_overlay_should_run_policy_flow(
        targeted_probe, cpe_configuration, topology_dict
    )


def _business_probe_rows_all_ok(rows: Any) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if not isinstance(row, dict):
            return False
        dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
        if dns.get("status") != "ok":
            return False
        for t in row.get("tcp") or []:
            if not isinstance(t, dict):
                return False
            if t.get("status") != "ok":
                return False
            td = t.get("data") if isinstance(t.get("data"), dict) else {}
            if td.get("port_open") is False:
                return False
    return True


@dataclass(frozen=True, slots=True)
class CommercialDeliveryPayload:
    """嵌入深度诊断拓扑字典的商用阅读层（序列化后供 Jinja2 使用）。"""

    trace_id: str
    headline: str
    subline: str
    checklist: tuple[Dict[str, str], ...] = field(default_factory=tuple)
    tunnel_peer_probes: tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    notices: tuple[str, ...] = field(default_factory=tuple)
    recommended_actions: tuple[str, ...] = field(default_factory=tuple)

    def as_template_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "headline": self.headline,
            "subline": self.subline,
            "checklist": list(self.checklist),
            "tunnel_peer_probes": list(self.tunnel_peer_probes),
            "notices": list(self.notices),
            "recommended_actions": list(self.recommended_actions),
        }


def build_commercial_delivery_payload(
    *,
    trace_id: str,
    diagnosis: DiagnosisResult,
    topology_dict: Dict[str, Any],
    targeted_probe: Optional[Dict[str, Any]],
    underlay_declared_business_focus: bool = False,
) -> Optional[CommercialDeliveryPayload]:
    """若存在 ``targeted_probe`` 业务上下文则构建载荷；否则返回 ``None``（纯深度诊断可不展示）。

    Args:
        underlay_declared_business_focus: 为 ``True`` 时（对声明目的地址的 nf_conntrack 采样**未见非空行**，
            与 ``business_joint_suppress_overlay_topology_presentation`` 对齐，**不将**声明单流与 CPE↔Hub 隧道/Overlay
            面绑定叙述），从 headline/核查表/推荐动作中去掉隧道 peer 与「隧道域」话术，仅保留与声明业务同口径的
            conntrack、DNS、NAT 提示。
    """
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return None
    if targeted_probe.get("status") not in ("ok", "partial"):
        return None
    data = targeted_probe.get("data") or {}
    if not isinstance(data, dict):
        return None
    rows = data.get("business_probes")
    if not rows or not isinstance(rows, list):
        return None

    raw_outputs: Dict[str, Any] = dict(data.get("raw_outputs") or {})
    biz_ips: List[str] = list(data.get("biz_target_ips") or [])
    if not biz_ips:
        for row in rows:
            if not isinstance(row, dict):
                continue
            dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
            dd = dns.get("data") if isinstance(dns.get("data"), dict) else {}
            for ip in dd.get("resolved_ips") or []:
                if ip and ip not in biz_ips:
                    biz_ips.append(str(ip))

    probe_domain = ""
    for row in rows:
        if isinstance(row, dict) and row.get("domain"):
            probe_domain = str(row.get("domain"))
            break

    pc_ip = _pc_primary_ip_from_topology(topology_dict)
    ct_blob = _nf_conntrack_blob_for_biz_ips(raw_outputs, biz_ips)
    ct_src = _first_conntrack_src_ip(ct_blob)
    ct_count = _conntrack_line_count(ct_blob)
    tunnel_rows = _collect_tunnel_peer_ping_rows(raw_outputs)
    if underlay_declared_business_focus:
        # 与 business_joint_should_present_overlay_tunnel_narrative 对齐：不向阅读层注入隧道 peer 行。
        tunnel_rows = []
    cause_ids = _cause_ids(diagnosis.root_causes)
    syn_only = _has_syn_only_conntrack(ct_blob)
    biz_all_ok = _business_probe_rows_all_ok(rows)

    notices: List[str] = []
    pc_ip_s = (pc_ip or "").strip()
    ct_has_pc_src = _conntrack_blob_has_src_ipv4(ct_blob, pc_ip_s) if pc_ip_s else False
    # 本机业务已通 + CPE 上可见发往业务目的之会话，但采样 conntrack 中从未出现 PC 主地址为 src：
    # 不能严格证明 PC↔CPE 间必有独立 NAT，但与上游 SNAT/三层网关改写源高度一致（见 INFO 文案）。
    show_upstream_nat_path_info = bool(
        biz_all_ok and pc_ip_s and ct_count > 0 and not ct_has_pc_src
    )
    if show_upstream_nat_path_info:
        ct_src_note = f"当前采样首条 src 为 `{ct_src}`。" if ct_src else "当前采样未能解析首条 src。"
        notices.append(
            "【INFO · 路径解读】本机业务探测已成功，且 CPE 上对业务目的地址的 nf_conntrack 采样可见相关会话，"
            f"但其中未见以 PC 快照主地址 `{pc_ip_s}` 为源（src）的条目；{ct_src_note}"
            " **仅凭该组合不能严格证明** PC 与 CPE 之间一定存在 NAT 设备（亦可能与透明代理、分流出口、"
            "会话展示字段或采样时刻有关）。**该形态与「PC 与 CPE 之间存在源地址改写（SNAT）或其它 L3 网关」"
            "在现网中最常见；建议在中间设备核对出站源 IP，并与 CPE 上 conntrack 的 src 对照复核。"
        )
    elif pc_ip and ct_src and pc_ip != ct_src:
        notices.append(
            f"源地址对齐：PC 快照主地址为 `{pc_ip}`，nf_conntrack 首条源为 `{ct_src}`。"
            " 若路径上存在 NAT 或探测经管理面发起，二者不一致属常见情况，请结合拓扑与接口解释。"
        )
    ipset_raw = str(raw_outputs.get("diagnose:ipset --list") or "")
    cdn_note = _ipset_cdn_notice(ipset_raw, biz_ips, probe_domain)
    if cdn_note:
        notices.append(cdn_note)

    # 主叙述与页首结论区共享单一事实源：避免「页首一种说法、交付摘要另一种说法」。
    headline, sub_bullets = build_joint_primary_narrative(
        tunnel_rows=tunnel_rows,
        conntrack_lines=ct_count,
        has_syn_only=syn_only,
        cause_ids=cause_ids,
        biz_all_ok=biz_all_ok,
        underlay_declared_business_focus=underlay_declared_business_focus,
    )

    subline = (
        f"Trace ID: {trace_id} · 本页为阅读层归纳；"
        f"规则结论见「根因分析」，证据见「拓扑后主动探测」与「原始命令输出」。"
    )

    checklist: List[Dict[str, str]] = []
    pc_ok = bool(topology_dict.get("pc_snapshot_included"))
    checklist.append(
        {
            "id": "T0",
            "label": "PC 观测是否纳入",
            "status": "是" if pc_ok else "否",
            "detail": "已纳入快照则利于路由/DNS/代理对齐；未纳入则置信度受限。",
        }
    )
    checklist.append(
        {
            "id": "T1",
            "label": "CPE 是否出现与业务目的 IP 相关的 conntrack 条目",
            "status": "是" if ct_count > 0 else "否",
            "detail": f"grep 命中约 {ct_count} 行（采样）；全量 conntrack 未采集。",
        }
    )
    if tunnel_rows:
        all_ok = all(r.get("status") == "ok" for r in tunnel_rows)
        checklist.append(
            {
                "id": "T2",
                "label": "隧道对端 ICMP 探针",
                "status": "是" if all_ok else ("部分" if any(r.get("status") == "ok" for r in tunnel_rows) else "否"),
                "detail": "仅探测隧道 peer，不对业务目的 IP 做 ICMP。",
            }
        )
    if biz_all_ok:
        t3_status = "是（本机探测）" if not (syn_only and ct_count > 0) else "本机通 / CPE 采样见 SYN"
        t3_detail = (
            "本机 TCP 已成功；若 conntrack 仍为 SYN-only，多为采样时刻不同步或目的为 CDN 共享 IP，请对照原始输出。"
        )
    else:
        t3_status = "否" if syn_only and ct_count > 0 else ("未知" if ct_count == 0 else "部分/已建立")
        t3_detail = "出现 ESTABLISHED 则视为握手已建立；仅 SYN_SENT/UNREPLIED 视为未完成。"
    checklist.append(
        {
            "id": "T3",
            "label": "TCP 是否完成握手（基于 conntrack 形态）",
            "status": t3_status,
            "detail": t3_detail,
        }
    )

    if biz_all_ok:
        actions = [
            "将本报告与现网变更窗口对齐留存；重大策略/NAT 变更后建议复跑同参数以对比。",
            "核对业务域名解析与 ipset/url-group 是否仍覆盖当前解析地址（CDN 场景尤需人工复核）。",
        ]
        if not underlay_declared_business_focus:
            actions.append(
                "若需证明隧道域内无丢包，可另行安排 Hub 侧或对端抓包，与本机探测结果交叉验证。"
            )
    else:
        actions = [
            "核对 url-group / ipset 与真实访问域名及解析 IP 是否一致（CDN 共享 IP 时需人工解释）。",
        ]
        if not underlay_declared_business_focus:
            actions[:0] = [
                "若隧道 peer ping 失败：先修 Underlay/隧道，再复测业务 TCP。",
                "若 peer 正常但 SYN 卡住：向线路/对端侧索取回程与目的侧 ACL/清洗策略，并在 CPE 出口抓包核对 SYN/SYN-ACK。",
            ]

    chk_tuple = tuple(checklist)
    tunnel_tuple = tuple(tunnel_rows)
    notice_tuple = tuple(notices + sub_bullets)
    action_tuple = tuple(actions)

    return CommercialDeliveryPayload(
        trace_id=trace_id,
        headline=headline,
        subline=subline,
        checklist=chk_tuple,
        tunnel_peer_probes=tunnel_tuple,
        notices=notice_tuple,
        recommended_actions=action_tuple,
    )
