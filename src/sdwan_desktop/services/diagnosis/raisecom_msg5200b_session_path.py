"""Raisecom MSG5200B：nf_conntrack 双向五元组路径旁证（L1，5200B-only）。

产品规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`` §2.1。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    _biz_target_ips_from_targeted_data,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    conntrack_destination_ipv4s_from_blob,
    pc_matches_sdwan_policy_source_prefix,
    tunnel_peer_and_overlay_address_set,
    _nf_conntrack_blob_for_biz_targets,
)

logger = logging.getLogger(__name__)

_IPV4 = r"(\d{1,3}(?:\.\d{1,3}){3})"
_PAIR_RE = re.compile(
    rf"\bsrc={_IPV4}\s+dst={_IPV4}\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ConntrackBidirectionalTuple:
    """单行 nf_conntrack 解析出的正向/回程地址对。"""

    forward_src: str
    forward_dst: str
    reply_src: Optional[str] = None
    reply_dst: Optional[str] = None
    raw_line: str = ""


@dataclass(slots=True)
class SessionPathEvidence:
    """L1 会话路径旁证（供 path_verdict 聚合）。"""

    has_sampling: bool
    overlay_path_confirmed: bool
    line_confirmed_count: int
    blob_all_dips_tunnel: bool
    policy_src_mismatch: bool
    forward_src_matches_pc: bool
    rule_branch: str
    sample_lines: List[str] = field(default_factory=list)
    summary: str = ""


def vxlan_logical_iface_ipv4_set(cpe: Optional[CpeConfiguration]) -> Set[str]:
    """从 ``cpe.interfaces`` 收集名称含 vxlan 的三层口 IPv4。"""
    out: Set[str] = set()
    if cpe is None:
        return out
    for iface in cpe.interfaces or []:
        name = (iface.name or "").lower()
        if "vxlan" not in name:
            continue
        ip = (iface.ip_address or "").strip()
        if ip:
            out.add(ip)
    return out


def parse_conntrack_line_bidirectional(line: str) -> Optional[ConntrackBidirectionalTuple]:
    """按出现顺序解析一行内第一对为正向、第二对为回程 ``src/dst``。"""
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


def _reply_hits_overlay_endpoint(
    tup: ConntrackBidirectionalTuple,
    vxlan_ips: Set[str],
    tunnel_set: Set[str],
) -> bool:
    for ip in (tup.reply_dst, tup.reply_src):
        if not ip:
            continue
        if ip in vxlan_ips or ip in tunnel_set:
            return True
    return False


def _line_confirms_overlay(
    tup: ConntrackBidirectionalTuple,
    biz_targets: Set[str],
    vxlan_ips: Set[str],
    tunnel_set: Set[str],
) -> bool:
    """同一条 conntrack 记录：正向 dst 为业务目标，回程与正向为同一流（reply.src=fwd.dst）。"""
    if tup.forward_dst not in biz_targets:
        return False
    if tup.reply_src is None and tup.reply_dst is None:
        return False
    # 排除同一行内拼接的多条单向会话（第二对 src 仍为内网侧、不等于正向 dst）
    if tup.reply_src is not None and tup.reply_src != tup.forward_dst:
        return False
    return _reply_hits_overlay_endpoint(tup, vxlan_ips, tunnel_set)


def evaluate_session_path_evidence(
    targeted_data: dict,
    cpe: Optional[CpeConfiguration],
    pc_ip: Optional[str],
) -> SessionPathEvidence:
    """评估 L1：双向 conntrack 行 + 整段 blob 隧道 DIP 兜底。"""
    blob = _nf_conntrack_blob_for_biz_targets(targeted_data)
    biz_targets = set(_biz_target_ips_from_targeted_data(targeted_data))
    tunnel_set = tunnel_peer_and_overlay_address_set(cpe) if cpe else set()
    vxlan_ips = vxlan_logical_iface_ipv4_set(cpe)
    policy_ok = pc_matches_sdwan_policy_source_prefix(pc_ip, cpe) if cpe else False
    # 无策略配置时 policy_ok 恒为 False，仍允许「全 DIP 隧道」兜底（与原 D2 单测一致）
    policy_mismatch = not policy_ok

    lines = [ln.strip() for ln in (blob or "").splitlines() if ln.strip()]
    sample_lines: List[str] = []
    line_hits = 0
    pc_src_seen = False

    for ln in lines:
        tup = parse_conntrack_line_bidirectional(ln)
        if tup is None:
            continue
        if pc_ip and tup.forward_src == pc_ip:
            pc_src_seen = True
        if _line_confirms_overlay(tup, biz_targets, vxlan_ips, tunnel_set):
            line_hits += 1
            if len(sample_lines) < 3:
                sample_lines.append(ln)

    dips = conntrack_destination_ipv4s_from_blob(blob)
    blob_tunnel = bool(dips) and all(d in tunnel_set for d in dips)
    overlay = line_hits > 0 or (policy_mismatch and blob_tunnel)

    if line_hits > 0:
        branch = "conntrack_bidirectional_vxlan"
        summary = (
            f"L1：{line_hits} 条会话行满足「正向 dst∈业务目标且回程经 vxlan/隧道端点」。"
        )
    elif blob_tunnel:
        branch = "conntrack_all_dip_tunnel"
        summary = "L1：采样全部 dst 均为隧道/overlay 下一跳（策略源未匹配兜底）。"
    else:
        branch = "conntrack_no_overlay_line"
        summary = "L1：未见单行双向 overlay 旁证。"

    logger.debug(
        "session_path: lines=%d line_hits=%d blob_tunnel=%s branch=%s",
        len(lines),
        line_hits,
        blob_tunnel,
        branch,
    )
    return SessionPathEvidence(
        has_sampling=bool(lines),
        overlay_path_confirmed=overlay,
        line_confirmed_count=line_hits,
        blob_all_dips_tunnel=blob_tunnel,
        policy_src_mismatch=policy_mismatch,
        forward_src_matches_pc=pc_src_seen,
        rule_branch=branch,
        sample_lines=sample_lines,
        summary=summary,
    )
