"""CPE NAT inside 启发式适用性（Overlay vs Internet）。"""

from __future__ import annotations

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, InterfaceInfo, NatRuleInfo
from sdwan_desktop.services.diagnosis.cpe_nat_heuristic import cpe_nat_inside_heuristic_applicable

_URL_GROUP_TIKTOK = """url-group liveBroadcast
tiktok.com
!
"""

_RC = """url-group liveBroadcast
 url match suffix
 priority 150
 exit
"""


def _raisecom_cpe() -> CpeConfiguration:
    return CpeConfiguration(
        vendor="raisecom",
        model="MSG5200B",
        version="1",
        hostname="cpe",
        interfaces=[InterfaceInfo(name="vxlan5", ip_address="8.1.3.2")],
        nat_rules=[NatRuleInfo(protocol="tcp", inside_addr="10.10.0.0/16", outside_addr="1.1.1.1")],
    )


def test_applicable_without_business_probe_context() -> None:
    cpe = _raisecom_cpe()
    assert cpe_nat_inside_heuristic_applicable(cpe_config=cpe, targeted_probe=None) is True


def test_not_applicable_when_5200b_url_group_matches_overlay_intent() -> None:
    cpe = _raisecom_cpe()
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "www.tiktok.com", "port": 443}],
            "raw_outputs": {
                "show url-group all domain all": _URL_GROUP_TIKTOK,
                "running-config": _RC,
            },
        },
    }
    topo = {"pc_node_id": "pc-1", "nodes": [{"id": "pc-1", "type": "pc", "ip_address": "192.168.1.100"}]}
    assert cpe_nat_inside_heuristic_applicable(cpe_config=cpe, targeted_probe=tp, topology_dict=topo) is False


def test_applicable_when_5200b_domain_not_in_url_group() -> None:
    cpe = _raisecom_cpe()
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "www.baidu.com", "port": 443}],
            "raw_outputs": {
                "show url-group all domain all": _URL_GROUP_TIKTOK,
                "running-config": _RC,
            },
        },
    }
    assert cpe_nat_inside_heuristic_applicable(cpe_config=cpe, targeted_probe=tp) is True


def test_not_applicable_when_overlay_gate_positive() -> None:
    cpe = _raisecom_cpe()
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "www.baidu.com", "port": 443}],
            "biz_target_ips": ["172.253.118.91"],
            "raw_outputs": {
                "show url-group all domain all": "url-group liveBroadcast\n!\n",
                "running-config": _RC,
                "diagnose:nf_conntrack grep 172.253.118.91": (
                    "tcp TIME_WAIT src=10.10.25.3 dst=172.253.118.91 sport=1 dport=443 "
                    "src=172.253.118.91 dst=8.1.3.2 sport=443 dport=1"
                ),
            },
        },
    }
    topo = {"pc_node_id": "pc-1", "nodes": [{"id": "pc-1", "type": "pc", "ip_address": "192.168.1.100"}]}
    assert cpe_nat_inside_heuristic_applicable(cpe_config=cpe, targeted_probe=tp, topology_dict=topo) is False
