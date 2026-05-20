"""Raisecom MSG5200B：iptables mangle MARK 旁证（L2，5200B-only）。

产品规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`` §2.2、§11。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_MANGLE_LINE = re.compile(
    r"^\s*(\d+[KMG]?)\s+(\d+[KMG]?)\s+\S+\s+\S+\s+\S+\s+\S+\s+.*?MARK\s+set\s+(0x[0-9a-fA-F]+)",
    re.IGNORECASE,
)
_IP_RULE_FWMARK = re.compile(
    r"fwmark\s+(0x[0-9a-fA-F]+)\s+lookup\s+(\d+)",
    re.IGNORECASE,
)

# url-group 名 → 期望 MARK（与 network_analysis §3 一致）
_GROUP_TO_MARK: Dict[str, str] = {
    "acceleratePlus": "0x66",
    "liveBroadcast": "0x67",
}


@dataclass(slots=True)
class MangleMarkRuleHit:
    """单条 mangle MARK 规则命中统计。"""

    mark: str
    pkts: str
    pkts_numeric: int
    raw_line: str


@dataclass(slots=True)
class MangleEvidence:
    """L2 mangle 旁证。"""

    blob_present: bool
    expected_mark: str
    expected_table: str
    observed_mark_with_traffic: str = ""
    ip_rule_excerpt: str = ""
    mark_rule_matched: bool = False
    summary: str = ""
    prerouting_hits: List[MangleMarkRuleHit] = field(default_factory=list)
    excerpts: List[str] = field(default_factory=list)


def _parse_pkt_count(token: str) -> int:
    """将 iptables -nvL 计数 token 转为近似整数（用于比较是否为零）。"""
    t = (token or "").strip().upper()
    if not t:
        return 0
    try:
        if t.endswith("K"):
            return int(float(t[:-1]) * 1000)
        if t.endswith("M"):
            return int(float(t[:-1]) * 1_000_000)
        if t.endswith("G"):
            return int(float(t[:-1]) * 1_000_000_000)
        return int(t)
    except ValueError:
        return 0


def _parse_mangle_blob(blob: str) -> List[MangleMarkRuleHit]:
    hits: List[MangleMarkRuleHit] = []
    if not (blob or "").strip():
        return hits
    in_prerouting = False
    for line in str(blob).splitlines():
        stripped = line.strip()
        if stripped.startswith("Chain PREROUTING"):
            in_prerouting = True
            continue
        if stripped.startswith("Chain ") and not stripped.startswith("Chain PREROUTING"):
            in_prerouting = False
        if not in_prerouting:
            continue
        m = _MANGLE_LINE.search(line)
        if not m:
            continue
        pkts_tok, _bytes_tok, mark = m.group(1), m.group(2), m.group(3).lower()
        hits.append(
            MangleMarkRuleHit(
                mark=mark,
                pkts=pkts_tok,
                pkts_numeric=_parse_pkt_count(pkts_tok),
                raw_line=stripped[:240],
            )
        )
    return hits


def _ip_rule_excerpt(blob: str, expected_mark: str) -> str:
    if not blob.strip():
        return ""
    for line in blob.splitlines():
        if expected_mark.lower() in line.lower() and "lookup" in line.lower():
            return line.strip()[:200]
    for m in _IP_RULE_FWMARK.finditer(blob):
        if m.group(1).lower() == expected_mark.lower():
            return m.group(0)
    return ""


def evaluate_mangle_evidence(
    *,
    mangle_blob: str,
    ip_rule_blob: str,
    effective_group: Optional[str],
    fwmark_hint: str = "",
    table_hint: str = "",
    security_chain_ok: bool = False,
    ipset_hit: bool = False,
) -> MangleEvidence:
    """评估 PREROUTING mangle 是否对生效组打出期望 MARK。

    Args:
        mangle_blob: ``diagnose:iptables -t mangle -nvL`` 输出。
        ip_rule_blob: ``diagnose:ip rule show`` 输出。
        effective_group: 生效 url-group 名。
        fwmark_hint: 来自 url_group 分析（如 0x66）。
        table_hint: 策略表号（如 99）。
        security_chain_ok: security-src 步是否允许打标（源+组启用且 PC 在名单或未启用校验）。
        ipset_hit: 业务 IP 是否在 ipset。
    """
    expected_mark = (fwmark_hint or "").strip().lower()
    if not expected_mark and effective_group:
        expected_mark = _GROUP_TO_MARK.get(effective_group, "").lower()
    expected_table = (table_hint or "").strip()

    blob_present = bool((mangle_blob or "").strip())
    prerouting_hits = _parse_mangle_blob(mangle_blob)
    excerpts = [h.raw_line for h in prerouting_hits[:4]]

    observed_with_traffic = ""
    for h in prerouting_hits:
        if h.pkts_numeric > 0:
            observed_with_traffic = h.mark
            break

    ip_excerpt = _ip_rule_excerpt(ip_rule_blob, expected_mark) if expected_mark else ""

    mark_matched = False
    summary_parts: List[str] = []

    if not blob_present:
        summary_parts.append("L2：未采集 mangle -nvL，无法核对 MARK 计数。")
    elif not expected_mark:
        summary_parts.append("L2：无生效 url-group，跳过 mangle 期望 MARK。")
    elif not security_chain_ok:
        summary_parts.append(
            "L2：security-ip 未满足，PREROUTING 不应命中该组 MARK 规则（符合未打标）。"
        )
        for h in prerouting_hits:
            if h.mark == expected_mark and h.pkts_numeric == 0:
                mark_matched = False
                break
    else:
        for h in prerouting_hits:
            if h.mark == expected_mark and h.pkts_numeric > 0:
                mark_matched = True
                summary_parts.append(
                    f"L2：PREROUTING 见 MARK {expected_mark} 且计数 {h.pkts}（生效组 {effective_group}）。"
                )
                break
        if not mark_matched and ipset_hit:
            summary_parts.append(
                f"L2：ipset 已命中但未见 MARK {expected_mark} 有效计数，可能未打标或采样窗口无流。"
            )
        elif not mark_matched:
            summary_parts.append(f"L2：未见 MARK {expected_mark} 有效计数。")

    if ip_excerpt:
        summary_parts.append(f"ip rule：{ip_excerpt}")

    return MangleEvidence(
        blob_present=blob_present,
        expected_mark=expected_mark,
        expected_table=expected_table,
        prerouting_hits=prerouting_hits,
        observed_mark_with_traffic=observed_with_traffic,
        ip_rule_excerpt=ip_excerpt,
        mark_rule_matched=mark_matched,
        summary="；".join(summary_parts) + "。",
        excerpts=excerpts,
    )
