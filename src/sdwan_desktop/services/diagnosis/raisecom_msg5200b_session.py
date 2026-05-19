"""Raisecom MSG5200B：会话采样工具与联合门控 re-export（5200B-only 门控见 business_gate）。

规则来源：
- ``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md``
- ``docs/rules/product_features/raisecom_msg5200b_network_analysis.md`` §5.2
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    _biz_target_ips_from_targeted_data,
)
from sdwan_desktop.services.diagnosis.joint_overlay_datapath_gate import (
    JointOverlayDatapathGate,
    compute_joint_overlay_datapath_gate,
)

# 模板/文档中的典型 overlay 下一跳（与 raisecom_msg5200b_network_analysis.md 表一致）
_MSG5200B_DEFAULT_OVERLAY_NEXTHOPS: frozenset[str] = frozenset(
    {"5.96.1.26", "5.100.1.18", "5.96.1.198", "5.100.1.174"}
)

_DST_IPV4 = re.compile(r"\bdst=(\d{1,3}(?:\.\d{1,3}){3})\b", re.IGNORECASE)

__all__ = [
    "JointOverlayDatapathGate",
    "compute_joint_overlay_datapath_gate",
    "joint_overlay_should_run_policy_flow",
    "is_raisecom_msg5200b_cpe",
    "pc_matches_sdwan_policy_source_prefix",
    "conntrack_destination_ipv4s_from_blob",
    "tunnel_peer_and_overlay_address_set",
    "_nf_conntrack_blob_for_biz_targets",
]


def is_raisecom_msg5200b_cpe(cpe: Optional[CpeConfiguration]) -> bool:
    if cpe is None:
        return False
    v = (cpe.vendor or "").lower()
    m = (cpe.model or "").upper()
    return "raisecom" in v or "5200" in m or "MSG5200" in m


def pc_matches_sdwan_policy_source_prefix(pc_ip: Optional[str], cpe: CpeConfiguration) -> bool:
    """PC 主地址是否与任一 SD-WAN 策略 source 前缀匹配（与 RootCauseEngine 启发式口径一致）。"""
    if not pc_ip or not cpe.sdwan_policies:
        return False
    for policy in cpe.sdwan_policies:
        if policy.source == "any":
            return True
        source_prefix = policy.source.split("/")[0] if "/" in policy.source else policy.source
        base = source_prefix.rsplit(".", 1)[0]
        if pc_ip.startswith(base):
            return True
    return False


def _nf_conntrack_blob_for_biz_targets(data: Dict[str, Any]) -> str:
    raw_outputs: Dict[str, Any] = dict(data.get("raw_outputs") or {})
    parts: List[str] = []
    for ip in _biz_target_ips_from_targeted_data(data):
        key = f"diagnose:nf_conntrack grep {ip}"
        if key in raw_outputs:
            parts.append(str(raw_outputs.get(key) or ""))
    return "\n".join(parts)


def conntrack_destination_ipv4s_from_blob(blob: str) -> List[str]:
    """从 nf_conntrack 多行文本中提取 dst= 后的 IPv4（保序去重）。"""
    seen: Set[str] = set()
    out: List[str] = []
    for m in _DST_IPV4.finditer(blob or ""):
        s = m.group(1)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def tunnel_peer_and_overlay_address_set(cpe: CpeConfiguration) -> Set[str]:
    """隧道对端 / overlay 下一跳候选（用于「全部为隧道地址」判定）。"""
    s: Set[str] = set(_MSG5200B_DEFAULT_OVERLAY_NEXTHOPS)
    for t in cpe.vpn_tunnels or []:
        rip = (t.remote_ip or "").strip()
        if rip:
            s.add(rip)
    return s


def joint_overlay_should_run_policy_flow(
    targeted_probe: Optional[Dict[str, Any]],
    cpe_configuration: Optional[CpeConfiguration] = None,
    topology_dict: Optional[Dict[str, Any]] = None,
) -> bool:
    """与 ``business_joint_should_present_overlay_tunnel_narrative`` 对齐的布尔门控。"""
    return compute_joint_overlay_datapath_gate(
        targeted_probe, cpe_configuration, topology_dict
    ).show_overlay_tunnel_strip
