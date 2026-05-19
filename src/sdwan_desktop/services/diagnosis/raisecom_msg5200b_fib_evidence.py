"""Raisecom MSG5200B：FIB / 策略表路径旁证（L3，5200B-only）。

产品规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`` §2.3。
"""

from __future__ import annotations

import ipaddress
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, RouteEntry
from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    _biz_target_ips_from_targeted_data,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    tunnel_peer_and_overlay_address_set,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session_path import (
    vxlan_logical_iface_ipv4_set,
)

logger = logging.getLogger(__name__)

_IPSET_MEMBER = re.compile(
    r"^(\d{1,3}(?:\.\d{1,3}){3})\s",
    re.MULTILINE,
)
_TABLE_DEFAULT = re.compile(
    r"default\s+via\s+(\d{1,3}(?:\.\d{1,3}){3})\s+dev\s+(\S+)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class FibEvidence:
    """L3 FIB 旁证。"""

    fib_suggests_overlay: bool
    egress_dev: str
    table_id: str
    next_hop: str
    biz_ip_in_ipset: bool
    ipset_hint: str
    summary: str
    excerpts: List[str] = field(default_factory=list)


def _parse_ipv4(ip: str) -> Optional[ipaddress.IPv4Address]:
    try:
        addr = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        return None
    return addr if isinstance(addr, ipaddress.IPv4Address) else None


def _route_prefix_len(dest: str) -> int:
    dest = (dest or "").strip()
    if "/" in dest:
        try:
            return ipaddress.ip_network(dest, strict=False).prefixlen
        except ValueError:
            return 0
    if dest:
        return 32
    return 0


def _route_covers_ip(route: RouteEntry, ip: ipaddress.IPv4Address) -> bool:
    dest = (route.destination or "").strip()
    if not dest:
        return False
    try:
        if "/" in dest:
            net = ipaddress.ip_network(dest, strict=False)
            return ip in net
        host = _parse_ipv4(dest)
        return host == ip
    except ValueError:
        return False


def _best_route_for_ip(
    routes: Sequence[RouteEntry],
    ip: ipaddress.IPv4Address,
) -> Optional[RouteEntry]:
    best: Optional[RouteEntry] = None
    best_len = -1
    for r in routes:
        if not _route_covers_ip(r, ip):
            continue
        plen = _route_prefix_len(r.destination or "")
        if plen > best_len:
            best_len = plen
            best = r
    return best


def _is_vxlan_dev(dev: Optional[str]) -> bool:
    return bool(dev) and "vxlan" in (dev or "").lower()


def _collect_routes(cpe: CpeConfiguration) -> List[RouteEntry]:
    routes = list(cpe.routes or [])
    raw = dict(cpe.raw_outputs or {})
    for key in ("show ip route", "show ip  route"):
        text = raw.get(key, "")
        if text and not routes:
            from sdwan_desktop.services.parser.vendor.raisecom_msg5200 import (
                RaisecomMsg5200Parser,
            )

            p = RaisecomMsg5200Parser()
            routes.extend(p.parse_routes(text))
    return routes


def _policy_table_defaults(cpe: CpeConfiguration) -> Dict[str, List[tuple[str, str]]]:
    """table_id -> [(next_hop, dev), ...] from raw diagnose output."""
    out: Dict[str, List[tuple[str, str]]] = {}
    raw = dict(cpe.raw_outputs or {})
    for tid, key in (
        ("99", "diagnose:ip route show table 99"),
        ("100", "diagnose:ip route show table 100"),
    ):
        text = raw.get(key, "")
        if not text:
            continue
        pairs: List[tuple[str, str]] = []
        for m in _TABLE_DEFAULT.finditer(text):
            pairs.append((m.group(1), m.group(2)))
        if pairs:
            out[tid] = pairs
    return out


def _biz_ips_in_ipset_blob(blob: str, biz_ips: Set[str]) -> tuple[bool, str]:
    if not blob or not biz_ips:
        return False, ""
    for ip in biz_ips:
        if re.search(rf"(?m)^{re.escape(ip)}\s", blob):
            if "liveBroadcast" in blob or "url_white_list_liveBroadcast" in blob:
                return True, "url_white_list_liveBroadcast"
            if "acceleratePlus" in blob or "url_white_list_acceleratePlus" in blob:
                return True, "url_white_list_acceleratePlus"
            return True, "ipset"
    return False, ""


def evaluate_fib_evidence(
    targeted_data: dict,
    cpe: Optional[CpeConfiguration],
) -> FibEvidence:
    """对声明业务 IP 评估 main / policy 表出向。"""
    biz_ips = set(_biz_target_ips_from_targeted_data(targeted_data))
    if not cpe or not biz_ips:
        return FibEvidence(
            fib_suggests_overlay=False,
            egress_dev="",
            table_id="",
            next_hop="",
            biz_ip_in_ipset=False,
            ipset_hint="",
            summary="L3：无 CPE 配置或业务 IP。",
        )

    raw_probe: Dict[str, Any] = dict(targeted_data.get("raw_outputs") or {})
    ipset_blob = str(
        raw_probe.get("diagnose:ipset --list")
        or dict(cpe.raw_outputs or {}).get("diagnose:ipset --list")
        or ""
    )
    in_ipset, ipset_hint = _biz_ips_in_ipset_blob(ipset_blob, biz_ips)

    routes = _collect_routes(cpe)
    vxlan_ips = vxlan_logical_iface_ipv4_set(cpe)
    tunnel_set = tunnel_peer_and_overlay_address_set(cpe)
    overlay_gw = vxlan_ips | tunnel_set

    table_defs = _policy_table_defaults(cpe)
    excerpts: List[str] = []
    raw = dict(cpe.raw_outputs or {})
    for key in (
        "show ip route",
        "show ip  route",
        "diagnose:ip route show table 99",
        "diagnose:ip route show table 100",
    ):
        text = str(raw.get(key) or "").strip()
        if not text:
            continue
        for line in text.splitlines()[:4]:
            line = line.strip()
            if line:
                excerpts.append(line)
                if len(excerpts) >= 6:
                    break
        if len(excerpts) >= 6:
            break
    egress_dev = ""
    next_hop = ""
    table_id = "main"
    suggests = False

    for biz in sorted(biz_ips):
        addr = _parse_ipv4(biz)
        if addr is None:
            continue
        best = _best_route_for_ip(routes, addr)
        if best and best.interface:
            egress_dev = best.interface
            next_hop = best.gateway or ""
            table_id = "main"
            if best.raw_line and len(excerpts) < 2:
                excerpts.append(best.raw_line.strip())
            if _is_vxlan_dev(egress_dev):
                suggests = True

        if in_ipset and table_defs:
            for tid, pairs in table_defs.items():
                for nh, dev in pairs:
                    if _is_vxlan_dev(dev):
                        suggests = True
                        egress_dev = dev
                        next_hop = nh
                        table_id = tid
                        break

    if not suggests and egress_dev and _is_vxlan_dev(egress_dev):
        suggests = True

    if not suggests and next_hop in overlay_gw:
        suggests = True

    summary_parts = [f"L3：业务 IP 出接口 `{egress_dev or '—'}`（表 {table_id}）"]
    if in_ipset:
        summary_parts.append(f"目的在 ipset（{ipset_hint or '命中'}）")
    if suggests:
        summary_parts.append("推断可走 Overlay/vxlan 面")
    else:
        summary_parts.append("未见 vxlan 出接口")

    return FibEvidence(
        fib_suggests_overlay=suggests,
        egress_dev=egress_dev,
        table_id=table_id,
        next_hop=next_hop,
        biz_ip_in_ipset=in_ipset,
        ipset_hint=ipset_hint,
        summary="；".join(summary_parts) + "。",
        excerpts=excerpts,
    )
