"""PC 侧业务探测 ``trace`` 行与拓扑/CPE 配置对照，归纳路径层证据。

与 ``spec/detail_function_design.md`` §2.2.2 对齐：traceroute **不**单独触发联合门控，
但可与 nf_conntrack / 隧道 ICMP 证据融合，用于 Overlay 示意条、拓扑着色与 BIZ-TCP 叙述。
规则补充见 ``docs/rules/product_features/raisecom_msg5200b_network_analysis.md``（会话 + 本机路径旁证）。
"""

from __future__ import annotations

import ipaddress
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple

EgressShape = Literal["", "wan_gateway", "early_public"]

from sdwan_desktop.core.types.cpe_config import CpeConfiguration

logger = logging.getLogger(__name__)

_DST_IPV4 = re.compile(r"\bsrc=(\d{1,3}(?:\.\d{1,3}){3})\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class BusinessTraceEvidence:
    """从 ``business_probes[].trace`` 与拓扑/CPE 上下文提炼的路径旁证（只读）。"""

    trace_available: bool
    """是否至少有一条成功的 traceroute 跳表。"""

    egress_past_cpe: bool
    """在 CPE 亲和地址之后出现非公网私网/隧道域外的下一跳（报文已离开 CPE 邻域）。"""

    overlay_hop_observed: bool
    """跳表中命中已知隧道对端或 Overlay 下一跳地址集。"""

    public_internet_after_cpe: bool
    """CPE 亲和跳之后出现公网地址（非 RFC1918 等）。"""

    cpe_affinity_hop_count: int
    """判定为 CPE/站点私网侧的跳数。"""

    last_responsive_hop_ip: Optional[str]
    target_reached: bool
    narrative_hint: str
    hop_ips_ordered: Tuple[str, ...] = field(default_factory=tuple)
    egress_shape: EgressShape = ""

    def as_dict(self) -> Dict[str, Any]:
        """写入 ``topology_dict`` / JSON 的摘要（不含完整 hops 数组）。"""
        return {
            "trace_available": self.trace_available,
            "egress_past_cpe": self.egress_past_cpe,
            "overlay_hop_observed": self.overlay_hop_observed,
            "public_internet_after_cpe": self.public_internet_after_cpe,
            "cpe_affinity_hop_count": self.cpe_affinity_hop_count,
            "last_responsive_hop_ip": self.last_responsive_hop_ip,
            "target_reached": self.target_reached,
            "narrative_hint": self.narrative_hint,
            "hop_ips_ordered": list(self.hop_ips_ordered),
            "egress_shape": self.egress_shape,
        }


def compute_egress_shape(
    trace_ev: BusinessTraceEvidence,
    topology_dict: Optional[Dict[str, Any]] = None,
) -> EgressShape:
    """Underlay 路径形态：wan_gateway（经 WAN 网关）或 early_public（早期公网跳）。"""
    if not trace_ev.trace_available or not trace_ev.egress_past_cpe:
        return ""
    gw_ip: Optional[str] = None
    if topology_dict:
        gw_id = topology_dict.get("gateway_node_id")
        if gw_id:
            for n in topology_dict.get("nodes") or []:
                if isinstance(n, dict) and n.get("id") == gw_id:
                    gw_ip = (n.get("ip_address") or "").strip() or None
                    break
    if gw_ip and gw_ip in trace_ev.hop_ips_ordered:
        return "wan_gateway"
    if trace_ev.public_internet_after_cpe:
        return "early_public"
    return ""


def _parse_ipv4(ip: Optional[str]) -> Optional[ipaddress.IPv4Address]:
    if not ip or ip in ("*", ""):
        return None
    try:
        addr = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        return None
    if isinstance(addr, ipaddress.IPv4Address):
        return addr
    return None


def _is_site_private(addr: ipaddress.IPv4Address) -> bool:
    """站点/私网：RFC1918、链路本地、以及常见 CPE 管理网段启发式。"""
    if addr.is_private or addr.is_link_local or addr.is_loopback:
        return True
    # 10.10.x.x 在本产品中常见于 PC/CPE 管理面（报告样例 10.10.25.1 / 10.10.100.x）
    if addr in ipaddress.ip_network("10.10.0.0/16"):
        return True
    return False


def _tunnel_overlay_address_set(cpe_configuration: Optional[CpeConfiguration]) -> Set[str]:
    """延迟导入，避免与 ``raisecom_msg5200b_session`` 循环依赖。"""
    if cpe_configuration is None:
        return set()
    from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
        tunnel_peer_and_overlay_address_set,
    )

    return tunnel_peer_and_overlay_address_set(cpe_configuration)


def _collect_cpe_affinity_ips(
    cpe_configuration: Optional[CpeConfiguration],
    topology_dict: Optional[Dict[str, Any]],
) -> Set[str]:
    """CPE 管理/WAN/隧道对端/Overlay 下一跳等与「设备侧」相关的 IPv4。"""
    ips: Set[str] = set()
    if cpe_configuration is not None:
        ips.update(_tunnel_overlay_address_set(cpe_configuration))
        for wan in cpe_configuration.wan_interfaces or []:
            a = (wan.ip_address or "").strip()
            if a:
                ips.add(a)
        for t in cpe_configuration.vpn_tunnels or []:
            rip = (t.remote_ip or "").strip()
            if rip:
                ips.add(rip)
    if topology_dict:
        for key in ("cpe_node_id", "gateway_node_id", "pc_node_id"):
            node_id = topology_dict.get(key)
            if not node_id:
                continue
            for n in topology_dict.get("nodes") or []:
                if not isinstance(n, dict) or n.get("id") != node_id:
                    continue
                nip = (n.get("ip_address") or "").strip()
                if nip:
                    ips.add(nip)
                for row in n.get("interfaces") or []:
                    if not isinstance(row, dict):
                        continue
                    for k in ("ip", "ip_address", "address"):
                        v = (row.get(k) or "").strip()
                        if v:
                            ips.add(v.split("/")[0])
    return ips


def _conntrack_internal_src_ips(data: Dict[str, Any]) -> Set[str]:
    """从 nf_conntrack grep 样例提取 ``src=``（CPE 上观测到的源地址）。"""
    out: Set[str] = set()
    raw = dict(data.get("raw_outputs") or {})
    for _k, blob in raw.items():
        if not str(_k).startswith("diagnose:nf_conntrack grep "):
            continue
        for m in _DST_IPV4.finditer(str(blob or "")):
            out.add(m.group(1))
    return out


def _iter_trace_hops_from_probes(data: Dict[str, Any]) -> List[Tuple[int, str]]:
    """合并所有 ``business_probes`` 行内 trace 跳表为 (hop, ip) 列表（保序）。"""
    ordered: List[Tuple[int, str]] = []
    rows = data.get("business_probes")
    if not isinstance(rows, list):
        return ordered
    for row in rows:
        if not isinstance(row, dict):
            continue
        for tr in row.get("trace") or []:
            if not isinstance(tr, dict) or tr.get("status") != "ok":
                continue
            td = tr.get("data") if isinstance(tr.get("data"), dict) else {}
            hops = td.get("hops") if isinstance(td.get("hops"), list) else []
            for h in hops:
                if not isinstance(h, dict):
                    continue
                hop_n = int(h.get("hop") or 0)
                ip = str(h.get("ip") or "").strip()
                if hop_n > 0 and ip and ip != "*":
                    ordered.append((hop_n, ip))
    # 按 hop 去重保序
    seen: Set[int] = set()
    dedup: List[Tuple[int, str]] = []
    for hop_n, ip in sorted(ordered, key=lambda x: x[0]):
        if hop_n in seen:
            continue
        seen.add(hop_n)
        dedup.append((hop_n, ip))
    return dedup


def analyze_business_trace_evidence(
    targeted_probe: Optional[Dict[str, Any]],
    cpe_configuration: Optional[CpeConfiguration] = None,
    topology_dict: Optional[Dict[str, Any]] = None,
) -> BusinessTraceEvidence:
    """解析 ``targeted_probe`` 中的 PC 侧 traceroute，与 CPE/拓扑地址集对照。

    Returns:
        ``BusinessTraceEvidence``；无 trace 时各布尔为 ``False``、``trace_available=False``。
    """
    empty = BusinessTraceEvidence(
        trace_available=False,
        egress_past_cpe=False,
        overlay_hop_observed=False,
        public_internet_after_cpe=False,
        cpe_affinity_hop_count=0,
        last_responsive_hop_ip=None,
        target_reached=False,
        narrative_hint="",
        egress_shape="",
    )
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return empty
    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return empty

    hop_list = _iter_trace_hops_from_probes(data)
    if not hop_list:
        return empty

    cpe_ips = _collect_cpe_affinity_ips(cpe_configuration, topology_dict)
    cpe_ips.update(_conntrack_internal_src_ips(data))

    overlay_set = _tunnel_overlay_address_set(cpe_configuration)

    hop_ips = [ip for _, ip in hop_list]
    last_ip = hop_ips[-1] if hop_ips else None

    target_reached = False
    rows = data.get("business_probes") or []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            for tr in row.get("trace") or []:
                if not isinstance(tr, dict):
                    continue
                td = tr.get("data") if isinstance(tr.get("data"), dict) else {}
                summ = td.get("summary") if isinstance(td.get("summary"), dict) else {}
                if summ.get("target_reached"):
                    target_reached = True

    cpe_affinity_count = 0
    overlay_hop = False
    for _hn, ip in hop_list:
        addr = _parse_ipv4(ip)
        if addr is None:
            continue
        if ip in cpe_ips or ip in overlay_set or _is_site_private(addr):
            cpe_affinity_count += 1
        if ip in overlay_set:
            overlay_hop = True

    egress_past = False
    public_after = False
    last_cpe_affinity_idx = -1
    for idx, (_hn, ip) in enumerate(hop_list):
        addr = _parse_ipv4(ip)
        if addr is None:
            continue
        if ip in cpe_ips or (addr and _is_site_private(addr)):
            last_cpe_affinity_idx = idx

    for idx in range(last_cpe_affinity_idx + 1, len(hop_list)):
        _hn, ip = hop_list[idx]
        addr = _parse_ipv4(ip)
        if addr is None:
            continue
        if ip in overlay_set:
            overlay_hop = True
        if not _is_site_private(addr) and ip not in cpe_ips:
            public_after = True
            if idx > last_cpe_affinity_idx:
                egress_past = True
            break

    hint_parts: List[str] = []
    if egress_past:
        hint_parts.append("PC 侧 traceroute 在 CPE/站点私网跳之后出现公网路径，报文已离开 CPE 邻域")
    if overlay_hop:
        hint_parts.append("跳表命中隧道/Overlay 相关地址")
    if target_reached:
        hint_parts.append("追踪标示已到达目的主机")
    elif last_ip:
        hint_parts.append(f"末跳响应地址 {last_ip}")
    narrative = "；".join(hint_parts) if hint_parts else "已采集 traceroute 跳表"

    provisional = BusinessTraceEvidence(
        trace_available=True,
        egress_past_cpe=egress_past,
        overlay_hop_observed=overlay_hop,
        public_internet_after_cpe=public_after,
        cpe_affinity_hop_count=cpe_affinity_count,
        last_responsive_hop_ip=last_ip,
        target_reached=target_reached,
        narrative_hint=narrative,
        hop_ips_ordered=tuple(hop_ips),
        egress_shape="",
    )
    shape = compute_egress_shape(provisional, topology_dict)
    logger.debug(
        "BusinessTraceEvidence: hops=%d egress_past_cpe=%s overlay_hop=%s shape=%s",
        len(hop_list),
        egress_past,
        overlay_hop,
        shape,
    )
    return BusinessTraceEvidence(
        trace_available=True,
        egress_past_cpe=egress_past,
        overlay_hop_observed=overlay_hop,
        public_internet_after_cpe=public_after,
        cpe_affinity_hop_count=cpe_affinity_count,
        last_responsive_hop_ip=last_ip,
        target_reached=target_reached,
        narrative_hint=narrative,
        hop_ips_ordered=tuple(hop_ips),
        egress_shape=shape,
    )
