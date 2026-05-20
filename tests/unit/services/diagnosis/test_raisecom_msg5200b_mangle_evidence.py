"""Tests for Raisecom 5200B mangle MARK evidence (L2)."""

from __future__ import annotations

from sdwan_desktop.services.diagnosis.raisecom_msg5200b_mangle_evidence import (
    evaluate_mangle_evidence,
)

_MANGLE_SNIPPET = """Chain PREROUTING (policy ACCEPT 109M packets, 56G bytes)
 pkts bytes target     prot opt in     out     source               destination
1090K  216M MARK       all  --  *      *       0.0.0.0/0            0.0.0.0/0            match-set security_ip_list_acceleratePlus src match-set url_white_list_acceleratePlus dst MARK set 0x66
Chain INPUT (policy ACCEPT 50M packets, 24G bytes)
"""

_IP_RULE_SNIPPET = """0:      from all lookup local
219:    from all fwmark 0x66 lookup 99
32766:  from all lookup main
"""


def test_mangle_mark_matched_with_traffic() -> None:
    ev = evaluate_mangle_evidence(
        mangle_blob=_MANGLE_SNIPPET,
        ip_rule_blob=_IP_RULE_SNIPPET,
        effective_group="acceleratePlus",
        fwmark_hint="0x66",
        table_hint="99",
        security_chain_ok=True,
        ipset_hit=True,
    )
    assert ev.mark_rule_matched is True
    assert ev.expected_mark == "0x66"
    assert "0x66" in ev.ip_rule_excerpt


def test_mangle_miss_when_no_counter() -> None:
    blob = """Chain PREROUTING (policy ACCEPT 1 packets, 1 bytes)
 pkts bytes target     prot opt in     out     source               destination
    0     0 MARK       all  --  *      *       0.0.0.0/0            0.0.0.0/0            MARK set 0x66
"""
    ev = evaluate_mangle_evidence(
        mangle_blob=blob,
        ip_rule_blob="",
        effective_group="acceleratePlus",
        fwmark_hint="0x66",
        security_chain_ok=True,
        ipset_hit=True,
    )
    assert ev.mark_rule_matched is False
