"""Raisecom 5200B：url-group 多组命中与优先级补充（5200B-only，不单独打开 Overlay）。

规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`` § D5。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 与 whole_config_5200b / mangle 顺序一致：priority 数值越大越优先（liveBroadcast 在前）
_DEFAULT_GROUP_PRIORITY: Dict[str, int] = {
    "liveBroadcast": 200,
    "acceleratePlus": 100,
}

_URL_GROUP_HEADER = re.compile(r"^url-group\s+(\S+)", re.MULTILINE)
_PRIORITY_IN_BLOCK = re.compile(r"^\s*priority\s+(\d+)", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class UrlGroupPriorityVerdict:
    """声明域名在 url-group 中的命中与生效组推断（补充叙述，非门控主判据）。"""

    domain: str
    matched_groups: Tuple[str, ...]
    effective_group: Optional[str]
    summary: str
    evidence_excerpt: str


def _parse_url_group_domains(blob: str) -> Dict[str, List[str]]:
    """解析 ``show url-group all domain all`` 为 group -> [domain, ...]。"""
    groups: Dict[str, List[str]] = {}
    if not (blob or "").strip():
        return groups
    current: Optional[str] = None
    for line in str(blob).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        m = _URL_GROUP_HEADER.match(stripped)
        if m:
            current = m.group(1)
            groups.setdefault(current, [])
            continue
        if current and stripped and not stripped.startswith("security"):
            dom = stripped.split()[0].lower().rstrip(".")
            if dom and dom not in groups[current]:
                groups[current].append(dom)
    return groups


def _group_priority(name: str, running_config: str) -> int:
    """从 running-config 块读取 priority，否则用 5200B 默认表。"""
    if running_config:
        pat = rf"url-group\s+{re.escape(name)}\s*\n(.*?)(?:^exit|\Z)"
        m = re.search(pat, running_config, re.MULTILINE | re.DOTALL)
        if m:
            pm = _PRIORITY_IN_BLOCK.search(m.group(1))
            if pm:
                return int(pm.group(1))
    return _DEFAULT_GROUP_PRIORITY.get(name, 0)


def evaluate_url_group_priority_for_domain(
    *,
    domain: str,
    raw_outputs: Dict[str, Any],
    running_config: str = "",
) -> Optional[UrlGroupPriorityVerdict]:
    """若声明域名出现在 url-group 列表中，返回多组/优先级补充结论。"""
    dom = (domain or "").strip().lower().rstrip(".")
    if not dom:
        return None
    blob = str(raw_outputs.get("show url-group all domain all") or "")
    if not blob.strip():
        return None
    groups_map = _parse_url_group_domains(blob)
    matched = [g for g, doms in groups_map.items() if dom in doms]
    if not matched:
        return None
    if len(matched) == 1:
        eff = matched[0]
        summary = f"声明域名「{domain}」列入 url-group「{eff}」（配置意图为 SD-WAN 业务域）。"
    else:
        ranked = sorted(
            matched,
            key=lambda g: _group_priority(g, running_config),
            reverse=True,
        )
        eff = ranked[0]
        summary = (
            f"声明域名「{domain}」同时出现在 url-group {matched}；"
            f"按 priority / PREROUTING 顺序推断生效组为「{eff}」（补充说明，不能单独推翻 D0）。"
        )
    excerpt_lines = [ln for ln in blob.splitlines() if dom in ln.lower() or "url-group" in ln][:12]
    return UrlGroupPriorityVerdict(
        domain=domain,
        matched_groups=tuple(matched),
        effective_group=eff,
        summary=summary,
        evidence_excerpt="\n".join(excerpt_lines),
    )


def probe_domain_from_targeted_data(data: Dict[str, Any]) -> str:
    for row in data.get("business_probes") or []:
        if isinstance(row, dict) and row.get("domain"):
            return str(row["domain"])
    return ""
