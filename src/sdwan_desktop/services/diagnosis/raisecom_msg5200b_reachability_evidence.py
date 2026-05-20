"""Raisecom MSG5200B：可达性阶段 S1/S2 旁证（5200B-only）。

S1：PC→CPE（conntrack 采样 + 本机探测）
S2：CPE→下一跳（FIB NH + ARP + 可选 ping）

产品规则：计划 §8.4、§9 Phase D；gate §11 扩展。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from sdwan_desktop.core.types.declared_business_path import ConfigIntent
from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    targeted_probe_has_business_target_conntrack_hits,
)

S1Status = Literal["reached", "not_reached_likely", "no_conntrack_sampling", "unknown"]
S2Status = Literal["reachable", "unreachable", "unknown"]

_ARP_LINE = re.compile(
    r"^(\d{1,3}(?:\.\d{1,3}){3})\s+\S+\s+.*?\b([RSD])\b",
    re.MULTILINE,
)
_PING_LOSS = re.compile(r"(\d+)%\s+packet\s+loss", re.IGNORECASE)
_PING_UNREACHABLE = re.compile(r"(?:100%\s+packet\s+loss|Destination\s+Host\s+Unreachable)", re.I)


@dataclass(slots=True)
class ReachabilityEvidence:
    """S1/S2 可达性裁决（与策略链并列）。"""

    s1_status: S1Status = "unknown"
    s1_summary: str = ""
    s2_status: S2Status = "unknown"
    s2_summary: str = ""
    primary_rule_case: str = ""
    next_hop_checked: str = ""


def _business_probe_layer_ok(data: Dict[str, Any]) -> bool:
    """L0 DNS+TCP 是否均视为可达（用于 S1 无 ct 时分级）。"""
    rows = data.get("business_probes")
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
        if dns.get("status") != "ok":
            return False
        tcp_rows = row.get("tcp") if isinstance(row.get("tcp"), list) else []
        if not tcp_rows:
            return False
        for t in tcp_rows:
            if not isinstance(t, dict):
                return False
            if t.get("status") != "ok":
                return False
            td = t.get("data") if isinstance(t.get("data"), dict) else {}
            if td.get("port_open") is False:
                return False
    return True


def _arp_reachable(arp_blob: str, nh: str) -> Optional[bool]:
    if not nh or not (arp_blob or "").strip():
        return None
    for m in _ARP_LINE.finditer(arp_blob):
        if m.group(1) == nh:
            return m.group(2).upper() == "R"
    return False


def _ping_blob_reachable(ping_blob: str) -> Optional[bool]:
    if not (ping_blob or "").strip():
        return None
    if _PING_UNREACHABLE.search(ping_blob):
        return False
    lm = _PING_LOSS.search(ping_blob)
    if lm:
        try:
            loss = int(lm.group(1))
            return loss < 100
        except ValueError:
            pass
    if re.search(r"\d+\s+packets?\s+transmitted.*\d+\s+received", ping_blob, re.I):
        return True
    return None


def evaluate_reachability_evidence(
    *,
    targeted_probe: Optional[Dict[str, Any]],
    config_intent: ConfigIntent,
    next_hop: str = "",
    egress_dev: str = "",
    link_protect_action_down: bool = False,
    arp_blob: str = "",
    ping_blobs: Optional[Dict[str, str]] = None,
) -> ReachabilityEvidence:
    """评估 S1 PC→CPE 与 S2 CPE→NH。"""
    ev = ReachabilityEvidence()
    tp = targeted_probe if isinstance(targeted_probe, dict) else None
    data = tp.get("data") if tp and isinstance(tp.get("data"), dict) else {}
    has_ct = targeted_probe_has_business_target_conntrack_hits(tp)
    probe_ok = _business_probe_layer_ok(data)

    if has_ct:
        ev.s1_status = "reached"
        ev.s1_summary = "S1：CPE 上对声明业务目的地址存在 conntrack 采样，流量已到达本 CPE。"
    elif not probe_ok:
        ev.s1_status = "unknown"
        ev.s1_summary = "S1：本机 DNS/TCP 未通过，优先按 L0 根因处理，不单独裁决未到 CPE。"
    else:
        ev.s1_status = "no_conntrack_sampling"
        ev.s1_summary = (
            "S1：本机探测可达但 CPE 无 conntrack 命中，可能为采样窗口无流、"
            "上游 NAT 后 CPE 未见 PC 源，或流量未达本 CPE。"
        )

    nh = (next_hop or "").strip()
    ev.next_hop_checked = nh
    if not nh:
        ev.s2_status = "unknown"
        ev.s2_summary = "S2：无 FIB 下一跳，跳过 CPE→NH 可达性核对。"
        return ev

    if link_protect_action_down and config_intent == "sdwan_overlay":
        ev.s2_status = "unreachable"
        ev.s2_summary = (
            f"S2：意图走 Overlay（出接口 {egress_dev or 'vxlan'}），"
            f"但 link-protect/出接口 down，下一跳 {nh} 可能不可达。"
        )
        ev.primary_rule_case = "raisecom_reachability_next_hop_unreachable"
        return ev

    ping_map = ping_blobs or {}
    ping_ok: Optional[bool] = None
    for key, blob in ping_map.items():
        if nh in key:
            ping_ok = _ping_blob_reachable(blob)
            break

    arp_ok = _arp_reachable(arp_blob, nh)
    if ping_ok is False or arp_ok is False:
        ev.s2_status = "unreachable"
        ev.s2_summary = f"S2：下一跳 {nh} ARP/探测不可达（出接口 {egress_dev or '—'}）。"
        ev.primary_rule_case = "raisecom_reachability_next_hop_unreachable"
    elif ping_ok is True or arp_ok is True:
        ev.s2_status = "reachable"
        ev.s2_summary = f"S2：下一跳 {nh} 在 ARP/探测中可达（出接口 {egress_dev or '—'}）。"
    else:
        ev.s2_status = "unknown"
        ev.s2_summary = f"S2：下一跳 {nh} 无 ARP/ ping 旁证（出接口 {egress_dev or '—'}）。"

    return ev
