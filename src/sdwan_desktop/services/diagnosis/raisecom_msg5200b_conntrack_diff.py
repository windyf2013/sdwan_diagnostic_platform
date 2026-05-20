"""Raisecom MSG5200B：nf_conntrack baseline/post 差异分析（5200B-only）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    _biz_target_ips_from_targeted_data,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    pc_matches_sdwan_policy_source_prefix,
)

_IPV4 = r"(\d{1,3}(?:\.\d{1,3}){3})"
_PAIR_RE = re.compile(
    rf"\bsrc={_IPV4}\s+dst={_IPV4}\b",
    re.IGNORECASE,
)
_DPORT = re.compile(r"\bdport=(\d+)\b", re.IGNORECASE)


@dataclass(slots=True)
class ConntrackBidirectionalTuple:
    forward_src: str
    forward_dst: str
    reply_src: Optional[str] = None
    reply_dst: Optional[str] = None
    raw_line: str = ""


def parse_conntrack_line_bidirectional(line: str) -> Optional[ConntrackBidirectionalTuple]:
    text = (line or "").strip()
    if not text:
        return None
    pairs: List[Tuple[str, str]] = [(m.group(1), m.group(2)) for m in _PAIR_RE.finditer(text)]
    if not pairs:
        return None
    fwd_src, fwd_dst = pairs[0]
    reply_src: Optional[str] = None
    reply_dst: Optional[str] = None
    if len(pairs) >= 2:
        reply_src, reply_dst = pairs[1]
    return ConntrackBidirectionalTuple(
        forward_src=fwd_src,
        forward_dst=fwd_dst,
        reply_src=reply_src,
        reply_dst=reply_dst,
        raw_line=text,
    )


@dataclass(slots=True)
class ConntrackDiffEvidence:
    has_baseline: bool
    has_post: bool
    delta_lines: List[str] = field(default_factory=list)
    matched_tuples: List[ConntrackBidirectionalTuple] = field(default_factory=list)
    used_diff: bool = False
    sip_mismatch_relaxed: bool = False
    summary: str = ""


def _normalize_line(line: str) -> str:
    return " ".join((line or "").split())


def _lines_from_blob(blob: str) -> List[str]:
    return [ln.strip() for ln in (blob or "").splitlines() if ln.strip()]


def _baseline_blob_for_ip(raw_outputs: Dict[str, Any], ip: str) -> str:
    return str(raw_outputs.get(f"diagnose:nf_conntrack baseline grep {ip}") or "")


def _post_blob_for_ip(raw_outputs: Dict[str, Any], ip: str) -> str:
    return str(raw_outputs.get(f"diagnose:nf_conntrack grep {ip}") or "")


def _delta_lines(baseline_lines: List[str], post_lines: List[str]) -> List[str]:
    base_norm = {_normalize_line(ln) for ln in baseline_lines}
    out: List[str] = []
    seen: Set[str] = set()
    for ln in post_lines:
        norm = _normalize_line(ln)
        if norm in base_norm or norm in seen:
            continue
        seen.add(norm)
        out.append(ln)
    return out


def _declared_ports_from_probes(data: Dict[str, Any]) -> Set[int]:
    ports: Set[int] = set()
    for row in data.get("business_probes") or []:
        if not isinstance(row, dict):
            continue
        p = row.get("port")
        if isinstance(p, int) and 1 <= p <= 65535:
            ports.add(p)
    return ports


def _dport_matches_declared(line: str, declared_ports: Set[int]) -> bool:
    if not declared_ports:
        return True
    m = _DPORT.search(line)
    if not m:
        return True
    try:
        return int(m.group(1)) in declared_ports
    except ValueError:
        return True


def evaluate_conntrack_diff_evidence(
    targeted_data: dict,
    cpe: Optional[CpeConfiguration],
    pc_ip: Optional[str],
) -> ConntrackDiffEvidence:
    """baseline vs post-tcp conntrack 差异；SIP 不匹配时放宽 src 判据。"""
    raw: Dict[str, Any] = dict(targeted_data.get("raw_outputs") or {})
    biz_ips = _biz_target_ips_from_targeted_data(targeted_data)
    declared_ports = _declared_ports_from_probes(targeted_data)

    has_baseline = False
    has_post = False
    all_delta: List[str] = []

    for ip in biz_ips:
        baseline_key = f"diagnose:nf_conntrack baseline grep {ip}"
        post_key = f"diagnose:nf_conntrack grep {ip}"
        if baseline_key in raw:
            has_baseline = True
        b_lines = _lines_from_blob(_baseline_blob_for_ip(raw, ip))
        p_lines = _lines_from_blob(_post_blob_for_ip(raw, ip))
        if post_key in raw or p_lines:
            has_post = True
        all_delta.extend(_delta_lines(b_lines, p_lines))

    policy_ok = pc_matches_sdwan_policy_source_prefix(pc_ip, cpe) if cpe else False
    sip_relaxed = not policy_ok

    matched: List[ConntrackBidirectionalTuple] = []
    biz_set = set(biz_ips)

    used_diff = has_baseline and has_post
    if used_diff:
        candidates = all_delta
    elif has_post:
        candidates = []
        for ip in biz_ips:
            candidates.extend(_lines_from_blob(_post_blob_for_ip(raw, ip)))
    else:
        candidates = []

    for ln in candidates:
        if not _dport_matches_declared(ln, declared_ports):
            continue
        tup = parse_conntrack_line_bidirectional(ln)
        if tup is None or tup.forward_dst not in biz_set:
            continue
        if not sip_relaxed and pc_ip and tup.forward_src != pc_ip:
            continue
        matched.append(tup)

    if matched:
        summary = (
            f"conntrack diff：{len(matched)} 条 delta 会话"
            + ("（SIP 放宽）" if sip_relaxed else "")
        )
    elif used_diff and has_post:
        summary = "conntrack diff：post 有采样但 delta 未匹配声明业务/port。"
    elif has_post:
        summary = "conntrack post 有采样；未使用 diff 或未命中。"
    else:
        summary = "conntrack diff：无 post 采样。"

    return ConntrackDiffEvidence(
        has_baseline=has_baseline,
        has_post=has_post,
        delta_lines=all_delta[:20],
        matched_tuples=matched,
        used_diff=used_diff,
        sip_mismatch_relaxed=sip_relaxed,
        summary=summary,
    )


def diff_evidence_to_dict(ev: ConntrackDiffEvidence) -> Dict[str, Any]:
    return {
        "has_baseline": ev.has_baseline,
        "has_post": ev.has_post,
        "used_diff": ev.used_diff,
        "sip_mismatch_relaxed": ev.sip_mismatch_relaxed,
        "delta_line_count": len(ev.delta_lines),
        "matched_count": len(ev.matched_tuples),
        "summary": ev.summary,
        "sample_delta_lines": ev.delta_lines[:5],
    }
