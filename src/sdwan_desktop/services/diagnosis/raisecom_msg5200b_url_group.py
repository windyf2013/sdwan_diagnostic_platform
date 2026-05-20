"""Raisecom 5200B：url-group 多组命中与优先级补充（5200B-only，不单独打开 Overlay）。

规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`` § D5、路径对账 §；
``url match {fuzzy|precise|suffix}`` 见 ``templates/whole_config_5200b.txt`` L426 与 network_analysis §4.1。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

UrlMatchMode = Literal["fuzzy", "precise", "suffix"]
_KNOWN_URL_MATCH_MODES = frozenset({"fuzzy", "precise", "suffix"})

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.core.types.declared_business_path import (
    MatchedUrlGroupInfo,
    PerGroupSecurityRow,
    UrlGroupAnalysis,
)
from sdwan_desktop.services.parser.vendor.raisecom_msg5200 import RaisecomMsg5200Parser

# 与 whole_config_5200b / mangle 顺序一致：priority 数值越大越优先（liveBroadcast 在前）
_DEFAULT_GROUP_PRIORITY: Dict[str, int] = {
    "liveBroadcast": 200,
    "acceleratePlus": 100,
}

# fwmark / 策略表 / 业务线展示（与 network_analysis §3 一致）
_GROUP_POLICY_HINTS: Dict[str, Tuple[str, str, str]] = {
    "acceleratePlus": ("0x66", "99", "跨境加速"),
    "liveBroadcast": ("0x67", "100", "直播"),
}

_URL_GROUP_HEADER = re.compile(r"^url-group\s+(\S+)", re.MULTILINE)
_PRIORITY_IN_BLOCK = re.compile(r"^\s*priority\s+(\d+)", re.MULTILINE)
_URL_MATCH_MODE_IN_BLOCK = re.compile(r"url\s+match\s+(\S+)", re.IGNORECASE)
_URL_GROUP_BLOCK = re.compile(
    r"url-group\s+(\S+)\s*\n(.*?)(?:^exit|\Z)",
    re.MULTILINE | re.DOTALL,
)

# 5200B 现网默认 suffix（running-config 未采到时）
_DEFAULT_URL_MATCH_MODE = "suffix"


@dataclass(frozen=True, slots=True)
class UrlGroupPriorityVerdict:
    """声明域名在 url-group 中的命中与生效组推断（补充叙述，非门控主判据）。"""

    domain: str
    matched_groups: Tuple[str, ...]
    effective_group: Optional[str]
    summary: str
    evidence_excerpt: str
    matched_patterns: Tuple[Tuple[str, str], ...] = ()
    """(group_name, list_pattern) 对，pattern 为 domain all 中命中的后缀/域条目。"""


def normalize_domain_for_match(domain: str) -> str:
    """FQDN 规范化（小写、去尾点）。"""
    return (domain or "").strip().lower().rstrip(".")


def normalize_url_match_mode(match_mode: str) -> UrlMatchMode:
    """规范化 CLI ``url match`` 参数；未知值回退 suffix 并记日志。"""
    mode = (match_mode or _DEFAULT_URL_MATCH_MODE).strip().lower()
    if mode in _KNOWN_URL_MATCH_MODES:
        return mode  # type: ignore[return-value]
    logger.warning("未知 url match 模式 %r，按 suffix 处理", match_mode)
    return "suffix"


def _precise_domain_match(declared: str, pattern: str) -> bool:
    """precise：声明 FQDN 与列表条目完全一致。"""
    return declared == pattern


def _suffix_domain_match(declared: str, pattern: str) -> bool:
    """suffix：列表条目为域名后缀（如 google.com ← music.google.com）。"""
    return declared == pattern or declared.endswith("." + pattern)


def _fuzzy_domain_match(declared: str, pattern: str) -> bool:
    """fuzzy：精确或后缀命中，或列表条目为声明域中的独立标签/标签子串。

    与设备语义对齐的保守实现：
    - 覆盖 precise / suffix 子情形；
    - 无点的条目（如 ``google``）可命中标签 ``google`` 或标签内包含该串（长度≥3）。
    """
    if _precise_domain_match(declared, pattern) or _suffix_domain_match(declared, pattern):
        return True
    labels = declared.split(".")
    if pattern in labels:
        return True
    if "." not in pattern and len(pattern) >= 3:
        return any(pattern in lbl for lbl in labels)
    return False


def domain_matches_url_group_entry(
    declared_domain: str,
    list_pattern: str,
    match_mode: str,
) -> bool:
    """判断声明域名是否命中 url-group 列表中的一条。

    Args:
        declared_domain: 业务探测声明 FQDN（如 ``music.google.com``）。
        list_pattern: ``show url-group all domain all`` 中的条目（如 ``google.com``）。
        match_mode: ``url match fuzzy|precise|suffix``（见 running-config）。
    """
    declared = normalize_domain_for_match(declared_domain)
    pattern = normalize_domain_for_match(list_pattern)
    if not declared or not pattern:
        return False
    mode = normalize_url_match_mode(match_mode)
    if mode == "precise":
        return _precise_domain_match(declared, pattern)
    if mode == "suffix":
        return _suffix_domain_match(declared, pattern)
    return _fuzzy_domain_match(declared, pattern)


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


def _parse_url_group_match_modes(running_config: str) -> Dict[str, str]:
    """从 running-config 解析各 url-group 的 ``url match`` 模式。"""
    modes: Dict[str, str] = {}
    if not (running_config or "").strip():
        return modes
    for m in _URL_GROUP_BLOCK.finditer(running_config):
        name = m.group(1)
        block = m.group(2)
        mm = _URL_MATCH_MODE_IN_BLOCK.search(block)
        modes[name] = normalize_url_match_mode(
            mm.group(1) if mm else _DEFAULT_URL_MATCH_MODE
        )
    return modes


def _resolve_match_modes(
    groups_map: Dict[str, List[str]],
    running_config: str,
    cpe: Optional[CpeConfiguration],
) -> Dict[str, str]:
    """合并 running-config 与解析器结构化结果；未配置组默认 suffix。"""
    modes = _parse_url_group_match_modes(running_config)
    detail_map = _url_group_detail_map(cpe) if cpe is not None else {}
    for name, detail in detail_map.items():
        if detail.url_match_mode:
            modes[name] = normalize_url_match_mode(str(detail.url_match_mode))
    for gname in groups_map:
        modes.setdefault(gname, _DEFAULT_URL_MATCH_MODE)
    return modes


def find_url_group_matches_for_domain(
    domain: str,
    groups_map: Dict[str, List[str]],
    match_modes: Dict[str, str],
) -> List[Tuple[str, str]]:
    """返回命中组及对应列表条目 ``[(group, matched_pattern), ...]``。"""
    matches: List[Tuple[str, str]] = []
    for gname, patterns in groups_map.items():
        mode = match_modes.get(gname, _DEFAULT_URL_MATCH_MODE)
        for pat in patterns:
            if domain_matches_url_group_entry(domain, pat, mode):
                matches.append((gname, pat))
                break
    return matches


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


def _format_match_summary(
    domain: str,
    matches: Sequence[Tuple[str, str]],
    eff: str,
    match_modes: Dict[str, str],
) -> str:
    if not matches:
        return ""

    def _mode_label(group: str) -> str:
        return normalize_url_match_mode(match_modes.get(group, _DEFAULT_URL_MATCH_MODE))

    if len(matches) == 1:
        g, pat = matches[0]
        ml = _mode_label(g)
        if normalize_domain_for_match(domain) == normalize_domain_for_match(pat):
            return (
                f"声明域名「{domain}」列入 url-group「{g}」"
                f"（url match {ml}，配置意图为 SD-WAN 业务域）。"
            )
        return (
            f"声明域名「{domain}」按 url match {ml} 命中 url-group「{g}」"
            f"（列表条目「{pat}」；配置意图为 SD-WAN 业务域）。"
        )
    groups = [g for g, _ in matches]
    pat_bits = ", ".join(
        f"「{g}」←「{p}」({_mode_label(g)})" for g, p in matches
    )
    return (
        f"声明域名「{domain}」按 url-group 规则同时命中 {groups}（{pat_bits}）；"
        f"按 priority / PREROUTING 顺序推断生效组为「{eff}」。"
    )


def evaluate_url_group_priority_for_domain(
    *,
    domain: str,
    raw_outputs: Dict[str, Any],
    running_config: str = "",
    cpe: Optional[CpeConfiguration] = None,
) -> Optional[UrlGroupPriorityVerdict]:
    """若声明域名按 url-group 规则（fuzzy/precise/suffix）命中，返回多组/优先级补充结论。"""
    dom = normalize_domain_for_match(domain)
    if not dom:
        return None
    blob = str(raw_outputs.get("show url-group all domain all") or "")
    if not blob.strip():
        return None
    groups_map = _parse_url_group_domains(blob)
    match_modes = _resolve_match_modes(groups_map, running_config, cpe)
    match_pairs = find_url_group_matches_for_domain(dom, groups_map, match_modes)
    if not match_pairs:
        return None

    matched = [g for g, _ in match_pairs]
    if len(matched) == 1:
        eff = matched[0]
    else:
        eff = sorted(
            matched,
            key=lambda g: _group_priority(g, running_config),
            reverse=True,
        )[0]
    summary = _format_match_summary(domain, match_pairs, eff, match_modes)
    excerpt_dom = normalize_domain_for_match(domain)
    excerpt_lines = [
        ln
        for ln in blob.splitlines()
        if excerpt_dom in ln.lower()
        or "url-group" in ln
        or any(p in ln.lower() for _, p in match_pairs)
    ][:12]
    return UrlGroupPriorityVerdict(
        domain=domain,
        matched_groups=tuple(matched),
        effective_group=eff,
        summary=summary,
        evidence_excerpt="\n".join(excerpt_lines),
        matched_patterns=tuple(match_pairs),
    )


def probe_domain_from_targeted_data(data: Dict[str, Any]) -> str:
    for row in data.get("business_probes") or []:
        if isinstance(row, dict) and row.get("domain"):
            return str(row["domain"])
    return ""


def _merged_raw_outputs(
    targeted_data: Dict[str, Any],
    cpe: Optional[CpeConfiguration],
) -> Dict[str, Any]:
    raw: Dict[str, Any] = dict(targeted_data.get("raw_outputs") or {})
    if cpe is not None:
        for k, v in dict(cpe.raw_outputs or {}).items():
            if k not in raw and isinstance(v, str):
                raw[k] = v
    return raw


def _url_group_detail_map(cpe: Optional[CpeConfiguration]) -> Dict[str, Any]:
    """从 CPE 原始输出解析 url-group 结构化配置（含 security-ip）。"""
    if cpe is None:
        return {}
    raw = dict(cpe.raw_outputs or {})
    rc = str(raw.get("show running-config") or "")
    sec = str(raw.get("show url-group all security-ip") or "")
    if not rc.strip():
        return {}
    groups = RaisecomMsg5200Parser().parse_url_groups_detail(rc, sec)
    return {g.group_name: g for g in groups if g.group_name}


def _pc_in_security_ips(pc_ip: Optional[str], security_ips: Sequence[str]) -> Optional[bool]:
    if not pc_ip:
        return None
    if not security_ips:
        return False
    return pc_ip.strip() in {str(x).strip() for x in security_ips}


def build_raisecom_msg5200b_url_group_analysis(
    *,
    domain: str,
    targeted_data: Dict[str, Any],
    cpe: Optional[CpeConfiguration],
    pc_ip: Optional[str] = None,
) -> Optional[UrlGroupAnalysis]:
    """域按 url-group 规则（fuzzy/precise/suffix）命中时构建 mandatory ``UrlGroupAnalysis``。"""
    dom = (domain or "").strip()
    if not dom:
        return None
    raw = _merged_raw_outputs(targeted_data, cpe)
    running_config = str(raw.get("running-config") or raw.get("show running-config") or "")
    verdict = evaluate_url_group_priority_for_domain(
        domain=dom,
        raw_outputs=raw,
        running_config=running_config,
        cpe=cpe,
    )
    if verdict is None:
        return UrlGroupAnalysis(
            domain=dom,
            domain_matched=False,
            summary=(
                f"声明域名「{dom}」未命中任一 url-group 列表"
                f"（已按 url match fuzzy/precise/suffix 核对 domain all）。"
            ),
            policy_intent_one_liner="未命中 url-group，预期走 main 表 Underlay 出口。",
        )

    detail_map = _url_group_detail_map(cpe)
    rc_modes = _parse_url_group_match_modes(running_config)
    pattern_by_group = {g: p for g, p in verdict.matched_patterns}
    matched_infos: List[MatchedUrlGroupInfo] = []
    per_sec: List[PerGroupSecurityRow] = []
    for gname in verdict.matched_groups:
        detail = detail_map.get(gname)
        pri = _group_priority(gname, running_config)
        hints = _GROUP_POLICY_HINTS.get(gname, ("", "", ""))
        sec_on = bool(detail.security_ip_enabled) if detail is not None else False
        sec_ips = list(detail.security_ips) if detail is not None else []
        match_mode = rc_modes.get(gname, _DEFAULT_URL_MATCH_MODE)
        if detail is not None and detail.url_match_mode:
            match_mode = normalize_url_match_mode(str(detail.url_match_mode))
        matched_infos.append(
            MatchedUrlGroupInfo(
                name=gname,
                priority=pri,
                security_ip_enabled=sec_on,
                fwmark_hint=hints[0],
                table_hint=hints[1],
                policy_line_hint=hints[2],
                url_match_mode=match_mode,
                matched_pattern=pattern_by_group.get(gname, ""),
            )
        )
        per_sec.append(
            PerGroupSecurityRow(
                group=gname,
                security_ip_enabled=sec_on,
                pc_in_list=_pc_in_security_ips(pc_ip, sec_ips) if sec_on else None,
            )
        )

    eff = verdict.effective_group
    eff_hints = _GROUP_POLICY_HINTS.get(eff or "", ("", "", "SD-WAN"))
    policy_line = (
        f"生效组「{eff}」：fwmark {eff_hints[0]} → 表 {eff_hints[1]}（{eff_hints[2]}）"
        if eff
        else ""
    )
    eff_pat = pattern_by_group.get(eff or "", "")
    eff_mode: str = _DEFAULT_URL_MATCH_MODE
    for mi in matched_infos:
        if mi.name == eff:
            eff_mode = mi.url_match_mode or _DEFAULT_URL_MATCH_MODE
            break
    if eff_pat and normalize_domain_for_match(dom) != normalize_domain_for_match(eff_pat):
        sel_reason = (
            f"声明域「{dom}」按 url match {eff_mode} 命中「{eff}」"
            f"（列表条目「{eff_pat}」，非逐字相等）。"
        )
    elif len(verdict.matched_groups) > 1:
        sel_reason = (
            f"声明域同时命中 url-group {list(verdict.matched_groups)}；"
            f"按 priority / PREROUTING 顺序推断生效组为「{eff}」。"
        )
    else:
        sel_reason = f"声明域列入 url-group「{eff}」。"

    return UrlGroupAnalysis(
        domain=dom,
        domain_matched=True,
        matched_groups=matched_infos,
        effective_group=eff,
        effective_selection_reason=sel_reason,
        per_group_security=per_sec,
        policy_intent_one_liner=policy_line,
        summary=verdict.summary,
    )
