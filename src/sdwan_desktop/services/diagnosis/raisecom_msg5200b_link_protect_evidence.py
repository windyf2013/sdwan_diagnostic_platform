"""Raisecom MSG5200B：link-protect 与 overlay 出接口状态（L4，5200B-only）。

产品规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`` §11.9.4。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sdwan_desktop.core.types.cpe_config import CpeConfiguration

_PROTECT_GROUP = re.compile(
    r"protect\s+group\s+(\S+)\s*:",
    re.IGNORECASE,
)
_ACTION_LINK = re.compile(
    r"current\s+action\s+link\s*:\s*(\S+)",
    re.IGNORECASE,
)
_ACTION_STATUS = re.compile(
    r"current\s+action\s+status\s*:\s*(\S+)",
    re.IGNORECASE,
)

_GROUP_VXLANS: Dict[str, Tuple[str, ...]] = {
    "acceleratePlus": ("vxlan2500133", "vxlan2600131"),
    "liveBroadcast": ("vxlan2500176", "vxlan2600170"),
}


@dataclass(slots=True)
class LinkProtectGroupState:
    """单保护组运行态。"""

    group_name: str
    action_link: str
    action_status: str


@dataclass(slots=True)
class LinkProtectEvidence:
    """L4 link-protect + 出接口 oper 旁证。"""

    blob_present: bool
    groups: List[LinkProtectGroupState] = field(default_factory=list)
    expected_vxlans: List[str] = field(default_factory=list)
    action_iface_down: bool = False
    egress_iface_oper_state: str = ""
    summary: str = ""
    excerpts: List[str] = field(default_factory=list)


def _parse_link_protect_blob(blob: str) -> List[LinkProtectGroupState]:
    groups: List[LinkProtectGroupState] = []
    if not (blob or "").strip():
        return groups
    current_name = ""
    action_link = ""
    action_status = ""
    for line in str(blob).splitlines():
        gm = _PROTECT_GROUP.search(line)
        if gm:
            if current_name:
                groups.append(
                    LinkProtectGroupState(
                        group_name=current_name,
                        action_link=action_link,
                        action_status=action_status,
                    )
                )
            current_name = gm.group(1)
            action_link = ""
            action_status = ""
            continue
        lm = _ACTION_LINK.search(line)
        if lm:
            action_link = lm.group(1)
        sm = _ACTION_STATUS.search(line)
        if sm:
            action_status = sm.group(1).lower()
    if current_name:
        groups.append(
            LinkProtectGroupState(
                group_name=current_name,
                action_link=action_link,
                action_status=action_status,
            )
        )
    return groups


def _iface_oper_map(cpe: Optional[CpeConfiguration]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if cpe is None:
        return out
    for iface in cpe.interfaces or []:
        name = (iface.name or "").strip()
        if name:
            out[name.lower()] = (iface.status or "unknown").lower()
    raw = str(dict(cpe.raw_outputs or {}).get("show interface") or "")
    if raw:
        for m in re.finditer(
            r"^(\S+)\s+.*?(?:line protocol|Link)\s+is\s+(up|down)",
            raw,
            re.IGNORECASE | re.MULTILINE,
        ):
            out[m.group(1).lower()] = m.group(2).lower()
    return out


def evaluate_link_protect_evidence(
    *,
    link_protect_blob: str,
    cpe: Optional[CpeConfiguration],
    effective_group: Optional[str] = None,
    fib_egress_dev: str = "",
) -> LinkProtectEvidence:
    """评估与生效 url-group 相关的 link-protect 与 vxlan/ge1 接口状态。"""
    groups = _parse_link_protect_blob(link_protect_blob)
    blob_present = bool(link_protect_blob.strip())
    expected = list(_GROUP_VXLANS.get(effective_group or "", ()))
    if fib_egress_dev and fib_egress_dev.lower().startswith("vxlan"):
        if fib_egress_dev not in expected:
            expected = [fib_egress_dev] + expected

    oper = _iface_oper_map(cpe)
    excerpts: List[str] = []
    for g in groups[:6]:
        excerpts.append(
            f"{g.group_name}: action={g.action_link} status={g.action_status or '?'}"
        )

    action_down = False
    oper_bits: List[str] = []
    relevant_groups = [
        g
        for g in groups
        if not expected or g.group_name in expected or g.action_link in expected
    ]
    if not relevant_groups and groups and expected:
        relevant_groups = [g for g in groups if any(v in g.group_name for v in expected)]

    for g in relevant_groups or groups:
        if g.action_status == "down":
            action_down = True
        if g.action_link:
            st = oper.get(g.action_link.lower(), "")
            if st:
                oper_bits.append(f"{g.action_link}={st}")

    for vx in expected:
        st = oper.get(vx.lower(), "")
        if st:
            oper_bits.append(f"{vx}={st}")
            if st == "down":
                action_down = True

    ge1_st = oper.get("ge1", "")
    if ge1_st:
        oper_bits.append(f"ge1={ge1_st}")

    egress_state = "；".join(dict.fromkeys(oper_bits)) if oper_bits else ""

    parts: List[str] = []
    if not blob_present:
        parts.append("L4：未采集 link-protect status。")
    elif action_down:
        parts.append("L4：link-protect 动作口或相关 vxlan 为 down，可能影响 Overlay 转发。")
    elif relevant_groups:
        up_links = [g.action_link for g in relevant_groups if g.action_status == "up"]
        if up_links:
            parts.append(f"L4：link-protect 动作口 {', '.join(up_links)} 为 up。")
        else:
            parts.append("L4：link-protect 已采样，动作口状态见证据节选。")
    else:
        parts.append("L4：link-protect 已采样，未匹配到生效组对应保护组。")

    if egress_state:
        parts.append(f"接口 oper：{egress_state}")

    return LinkProtectEvidence(
        blob_present=blob_present,
        groups=groups,
        expected_vxlans=expected,
        action_iface_down=action_down,
        egress_iface_oper_state=egress_state,
        summary="；".join(parts) + "。",
        excerpts=excerpts,
    )
