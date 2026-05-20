"""Tests for Raisecom 5200B policy chain contrast and declared path analysis."""

from __future__ import annotations

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_declared_path_analysis import (
    analyze_raisecom_msg5200b_declared_business_path,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_url_group import (
    build_raisecom_msg5200b_url_group_analysis,
)


def _url_group_domain_blob(domain: str, group: str) -> str:
    return f"url-group {group}\n{domain}\nexit\n"


def _security_ip_blob(group: str, ip: str) -> str:
    return f"url-group {group}\n{ip}\n"


def test_security_ip_miss_breakpoint_and_mismatch() -> None:
    cpe = CpeConfiguration(vendor="raisecom", model="MSG5200B")
    cpe.raw_outputs = {
        "show running-config": (
            "url-group acceleratePlus\n security ip enable\n priority 100\nexit\n"
        ),
        "show url-group all security-ip": _security_ip_blob("acceleratePlus", "192.168.54.1"),
        "show url-group all domain all": _url_group_domain_blob("biz.example", "acceleratePlus"),
    }
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "biz.example", "port": 443}],
            "biz_target_ips": ["203.0.113.10"],
            "raw_outputs": {
                "show url-group all domain all": cpe.raw_outputs["show url-group all domain all"],
                "diagnose:nf_conntrack grep 203.0.113.10": "",
                "diagnose:ipset --list": "",
            },
        },
    }
    topo = {
        "pc_node_id": "pc-1",
        "nodes": [{"id": "pc-1", "type": "pc", "ip_address": "192.168.54.99"}],
    }
    analysis = analyze_raisecom_msg5200b_declared_business_path(tp, cpe, topo)
    assert analysis.status == "ok"
    assert analysis.config_intent == "sdwan_overlay"
    assert analysis.reconcile.outcome == "mismatch"
    assert analysis.reconcile.break_point == "source_not_in_url_group_security_ip"
    assert analysis.url_group_analysis is not None
    assert analysis.url_group_analysis.domain_matched is True
    assert "security-ip" in (analysis.reconcile.summary_for_delivery or "")


def test_mangle_match_in_policy_chain() -> None:
    cpe = CpeConfiguration(vendor="raisecom", model="MSG5200B")
    pc_ip = "192.168.54.17"
    cpe.raw_outputs = {
        "show running-config": (
            "url-group acceleratePlus\n security ip enable\n priority 100\nexit\n"
        ),
        "show url-group all security-ip": _security_ip_blob("acceleratePlus", pc_ip),
        "show url-group all domain all": _url_group_domain_blob("biz.example", "acceleratePlus"),
    }
    mangle = """Chain PREROUTING (policy ACCEPT 1 packets, 1 bytes)
 pkts bytes target     prot opt in     out     source               destination
1090K  216M MARK       all  --  *      *       0.0.0.0/0            0.0.0.0/0            MARK set 0x66
"""
    ip_rule = "219:    from all fwmark 0x66 lookup 99\n"
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "biz.example", "port": 443}],
            "biz_target_ips": ["203.0.113.10"],
            "raw_outputs": {
                "show url-group all domain all": cpe.raw_outputs["show url-group all domain all"],
                "diagnose:nf_conntrack grep 203.0.113.10": "",
                "diagnose:ipset --list": "Members:\n203.0.113.10 timeout 0\n",
                "diagnose:iptables -t mangle -nvL": mangle,
                "diagnose:ip rule show": ip_rule,
            },
        },
    }
    topo = {
        "pc_node_id": "pc-1",
        "nodes": [{"id": "pc-1", "type": "pc", "ip_address": pc_ip}],
    }
    analysis = analyze_raisecom_msg5200b_declared_business_path(tp, cpe, topo)
    stages = [s.stage_id for s in analysis.policy_chain_contrast]
    assert "mangle" in stages
    assert "ip_rule" in stages
    mangle_step = next(s for s in analysis.policy_chain_contrast if s.stage_id == "mangle")
    assert mangle_step.runtime_status == "match"


def test_domain_not_in_url_group_internet_intent() -> None:
    cpe = CpeConfiguration(vendor="raisecom", model="MSG5200B")
    data = {
        "business_probes": [{"domain": "plain.example", "port": 443}],
        "biz_target_ips": ["203.0.113.20"],
        "raw_outputs": {
            "show url-group all domain all": _url_group_domain_blob("other.example", "acceleratePlus"),
            "diagnose:nf_conntrack grep 203.0.113.20": "",
        },
    }
    ug = build_raisecom_msg5200b_url_group_analysis(
        domain="plain.example",
        targeted_data=data,
        cpe=cpe,
        pc_ip="10.0.0.1",
    )
    assert ug is not None
    assert ug.domain_matched is False
    assert ug.domain_matched is False
    assert "未命中" in ug.summary or "suffix" in ug.summary
