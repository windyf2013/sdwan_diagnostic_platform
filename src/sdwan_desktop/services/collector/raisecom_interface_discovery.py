"""Raisecom 5200A/B：根据已有采集输出推断需补采的 ``show interface <name>`` 目标。

业务 underlay 出口通常为 ``ge1``（见 ``templates/whole_config_5200b.txt``）；Overlay 接口名
（vxlan / ipsec / l2tp 等）需从 ``running-config``、``show ip route``、``show link detect``、
策略路由表输出中提取，再在 enable 视图执行 ``show interface <ifname>``。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

# 与主模板已固定采集的接口去重，避免重复执行。
_DEFAULT_STATIC_IFACES: Set[str] = {"vlan1", "ge1"}

_IFACE_NAME_RE = re.compile(
    r"(?m)^interface\s+(vxlan\S+|ipsec\S+|l2tp\S+|tunnel\S+)\s*$",
    re.IGNORECASE,
)
_DEV_RE = re.compile(
    r"\bdev\s+(vxlan\S+|ipsec\S+|l2tp\S+|tunnel\S+)\b",
    re.IGNORECASE,
)
_MASTER_RE = re.compile(
    r"\bmaster\s+(vxlan\S+|ipsec\S+|l2tp\S+|tunnel\S+)\b",
    re.IGNORECASE,
)


def discover_raisecom_extra_interface_names(
    raw_outputs: Dict[str, str],
    *,
    max_interfaces: int = 24,
) -> List[str]:
    """从原始输出推断需补采的接口名（vxlan/ipsec/l2tp/tunnel* 等）。"""
    names: Set[str] = set()
    rc = raw_outputs.get("show running-config") or ""
    for m in _IFACE_NAME_RE.finditer(rc):
        names.add(m.group(1).strip())

    blobs: List[str] = [
        raw_outputs.get("show ip route") or "",
        raw_outputs.get("show link detect") or "",
        raw_outputs.get("diagnose:ip route show table 99") or "",
        raw_outputs.get("diagnose:ip route show table 100") or "",
    ]
    text = "\n".join(blobs)
    for rx in (_DEV_RE, _MASTER_RE):
        for m in rx.finditer(text):
            names.add(m.group(1).strip())

    names -= _DEFAULT_STATIC_IFACES
    ordered = sorted(names)
    if len(ordered) > max_interfaces:
        ordered = ordered[:max_interfaces]
    return ordered


def build_raisecom_extra_show_interface_commands(raw_outputs: Dict[str, str]) -> List[Dict[str, Any]]:
    """生成与 ``CpeCollector._execute_commands`` 兼容的补采命令列表。"""
    cmds: List[Dict[str, Any]] = []
    for ifname in discover_raisecom_extra_interface_names(raw_outputs):
        key = f"show interface {ifname}"
        if key in raw_outputs and (raw_outputs.get(key) or "").strip():
            continue
        cmds.append(
            {
                "name": key,
                "priority": 4,
                "optional": True,
                "save_as": key,
            }
        )
    return cmds
