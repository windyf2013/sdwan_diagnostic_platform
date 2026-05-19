"""将 PC 快照规范为 ``TopologyBuilder`` 所需的扁平 PC 数据（与深度诊断共用）。"""

from __future__ import annotations

import ipaddress
from typing import Any, Optional


def ipv4_same_slash24(a: Optional[str], b: Optional[str]) -> bool:
    """两 IPv4 是否同一 /24（供拓扑报告等复用）。"""
    return _pc_ipv4_same_slash24(a, b)


def _pc_ipv4_same_slash24(a: Optional[str], b: Optional[str]) -> bool:
    """判断两 IPv4 是否同一 /24（与拓扑层一致，用于 PC 主地址与网关同网段判定）。"""
    if not a or not b:
        return False
    try:
        pa = ipaddress.ip_address(a)
        pb = ipaddress.ip_address(b)
        if not isinstance(pa, ipaddress.IPv4Address) or not isinstance(pb, ipaddress.IPv4Address):
            return False
        return (int(pa) >> 8) == (int(pb) >> 8)
    except ValueError:
        return False


def _pc_ipv4_address(ip: str) -> Optional[ipaddress.IPv4Address]:
    try:
        addr = ipaddress.ip_address(ip)
        return addr if isinstance(addr, ipaddress.IPv4Address) else None
    except ValueError:
        return None


def _snapshot_default_gateway_ipv4(snapshot_dict: dict) -> Optional[str]:
    """从网卡、ip_config、默认路由中推断 IPv4 默认网关（优先已连接且配置了网关的网卡）。"""
    for a in snapshot_dict.get("adapters") or []:
        if not isinstance(a, dict) or not a.get("is_connected"):
            continue
        g = a.get("default_gateway")
        if g and _pc_ipv4_address(g):
            return g
    ip_cfg = snapshot_dict.get("ip_config") or {}
    if isinstance(ip_cfg, dict):
        g = ip_cfg.get("default_gateway")
        if g and _pc_ipv4_address(g):
            return g
    for r in snapshot_dict.get("routes") or []:
        if not isinstance(r, dict):
            continue
        if r.get("destination") == "0.0.0.0" and r.get("netmask") == "0.0.0.0":
            g = r.get("gateway")
            if g and _pc_ipv4_address(g):
                return g
    return None


def snapshot_to_topology_input(snapshot_obj: Any) -> dict:
    """将 SystemInfoSnapshot（或 dict）转为 TopologyBuilder 期望的扁平 PC 数据。

    主 IPv4 选取：优先与默认网关同 /24 的已连接网卡地址（业务出口常见），
    其次带 default_gateway 的网卡上首个可用地址，再退回旧逻辑。
    """
    if snapshot_obj is None:
        return {}

    if hasattr(snapshot_obj, "to_dict"):
        snapshot_dict = snapshot_obj.to_dict()
    elif isinstance(snapshot_obj, dict):
        snapshot_dict = snapshot_obj
    else:
        return {}

    adapters = snapshot_dict.get("adapters") or []
    hostname = snapshot_dict.get("hostname") or "unknown-pc"
    os_name = snapshot_dict.get("os_version") or "unknown"
    default_gw = _snapshot_default_gateway_ipv4(snapshot_dict)

    interfaces: list[str] = []
    for adapter in adapters:
        if not isinstance(adapter, dict):
            continue
        for ip in adapter.get("ip_addresses") or []:
            if ip and ip not in interfaces:
                interfaces.append(ip)

    scored: list[tuple[int, str, str]] = []
    for adapter in adapters:
        if not isinstance(adapter, dict):
            continue
        name = adapter.get("name", "") or ""
        connected = bool(adapter.get("is_connected"))
        ad_gw = adapter.get("default_gateway")
        for ip in adapter.get("ip_addresses") or []:
            if not ip or ip.startswith("169.254."):
                continue
            if not _pc_ipv4_address(ip):
                continue
            score = 0
            if default_gw and _pc_ipv4_same_slash24(ip, default_gw):
                score += 200
            if ad_gw and _pc_ipv4_same_slash24(ip, ad_gw):
                score += 80
            if connected:
                score += 10
            scored.append((score, ip, name))

    scored.sort(key=lambda x: (-x[0], x[1]))
    primary_ip: Optional[str] = None
    primary_iface = ""
    if scored:
        primary_ip, primary_iface = scored[0][1], scored[0][2]
    else:
        for adapter in adapters:
            if not isinstance(adapter, dict) or not adapter.get("is_connected"):
                continue
            for ip in adapter.get("ip_addresses") or []:
                if ip and not ip.startswith("169.254.") and _pc_ipv4_address(ip):
                    primary_ip = ip
                    primary_iface = adapter.get("name", "") or ""
                    break
            if primary_ip:
                break
        if not primary_ip and interfaces:
            for ip in interfaces:
                if _pc_ipv4_address(ip):
                    primary_ip = ip
                    break
            if not primary_ip:
                primary_ip = interfaces[0]

    arp_table: list[dict[str, str]] = []
    for item in snapshot_dict.get("arp_table") or []:
        if isinstance(item, dict):
            arp_table.append(
                {
                    "ip_address": item.get("ip_address") or "",
                    "mac_address": item.get("mac_address") or "",
                    "interface": item.get("interface") or "",
                }
            )

    return {
        "hostname": hostname,
        "primary_ip": primary_ip,
        "interfaces": interfaces,
        "os": os_name,
        "primary_interface": primary_iface,
        "default_gateway": default_gw,
        "arp_table": arp_table,
    }
