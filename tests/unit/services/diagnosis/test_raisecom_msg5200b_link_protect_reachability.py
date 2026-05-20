"""Tests for Raisecom 5200B L4 link-protect and S1/S2 reachability (Phase D)."""

from __future__ import annotations

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, InterfaceInfo
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_declared_path_analysis import (
    analyze_raisecom_msg5200b_declared_business_path,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_link_protect_evidence import (
    evaluate_link_protect_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_reachability_evidence import (
    evaluate_reachability_evidence,
)

_LINK_PROTECT_UP = """protect group vxlan2500133 :
  current action link   : vxlan2500133
  current action status : up
"""

_LINK_PROTECT_DOWN = """protect group vxlan2500133 :
  current action link   : vxlan2500133
  current action status : down
"""


def test_link_protect_down_sets_action_iface_down() -> None:
    cpe = CpeConfiguration(
        vendor="raisecom",
        model="MSG5200B",
        interfaces=[
            InterfaceInfo(name="vxlan2500133", status="down"),
        ],
    )
    ev = evaluate_link_protect_evidence(
        link_protect_blob=_LINK_PROTECT_DOWN,
        cpe=cpe,
        effective_group="acceleratePlus",
        fib_egress_dev="vxlan2500133",
    )
    assert ev.action_iface_down is True
    assert "down" in ev.summary


def test_s2_unreachable_when_arp_not_reachable() -> None:
    ev = evaluate_reachability_evidence(
        targeted_probe={"status": "ok", "data": {"business_probes": [], "biz_target_ips": ["1.1.1.1"]}},
        config_intent="sdwan_overlay",
        next_hop="5.96.1.26",
        egress_dev="vxlan2500133",
        arp_blob="IP Address       HW Address\n192.168.1.1    aa:bb:cc:dd:ee:ff",
    )
    assert ev.s2_status == "unreachable"
    assert ev.primary_rule_case == "raisecom_reachability_next_hop_unreachable"


def test_declared_path_overlay_iface_breakpoint() -> None:
    cpe = CpeConfiguration(vendor="raisecom", model="MSG5200B")
    cpe.raw_outputs = {
        "show running-config": "url-group acceleratePlus\n security ip enable\nexit\n",
        "show url-group all security-ip": "url-group acceleratePlus\n192.168.54.1\n",
        "show url-group all domain all": "url-group acceleratePlus\nbiz.example\nexit\n",
    }
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "biz.example", "port": 443, "dns": {"status": "ok"}, "tcp": [{"status": "ok", "data": {"port_open": True}}]}],
            "biz_target_ips": ["203.0.113.10"],
            "raw_outputs": {
                "show url-group all domain all": cpe.raw_outputs["show url-group all domain all"],
                "diagnose:nf_conntrack grep 203.0.113.10": "",
                "diagnose:ipset --list": "Members:\n203.0.113.10\n",
                "diagnose:iptables -t mangle -nvL": "",
                "diagnose:ip rule show": "",
                "show link-protect status": _LINK_PROTECT_DOWN,
            },
        },
    }
    topo = {
        "pc_node_id": "pc-1",
        "nodes": [{"id": "pc-1", "type": "pc", "ip_address": "192.168.54.1"}],
    }
    analysis = analyze_raisecom_msg5200b_declared_business_path(tp, cpe, topo)
    stage_ids = [s.stage_id for s in analysis.policy_chain_contrast]
    assert "overlay_iface" in stage_ids
    assert analysis.reconcile.break_point == "overlay_iface_down_link_protect"
    assert analysis.url_group_analysis is not None
    assert analysis.url_group_analysis.link_protect_summary
