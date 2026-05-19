"""raisecom_msg5200b_path_verdict 证据链载荷。"""

from __future__ import annotations

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, InterfaceInfo
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_path_verdict import (
    build_joint_path_evidence_dict,
    compute_raisecom_msg5200b_path_verdict,
)


def test_build_joint_path_evidence_dict_193136() -> None:
    cpe = CpeConfiguration(
        vendor="raisecom",
        model="MSG5200B",
        version="1",
        hostname="cpe",
        interfaces=[InterfaceInfo(name="vxlan5", ip_address="8.1.3.2")],
    )
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "youtube.com", "port": 443}],
            "biz_target_ips": ["172.253.118.91"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 172.253.118.91": (
                    "tcp TIME_WAIT src=10.10.25.3 dst=172.253.118.91 sport=1 dport=443 "
                    "src=172.253.118.91 dst=8.1.3.2 sport=443 dport=1"
                ),
            },
        },
    }
    topo = {"pc_node_id": "pc-1", "nodes": [{"id": "pc-1", "type": "pc", "ip_address": "10.10.100.161"}]}
    gate = compute_raisecom_msg5200b_path_verdict(tp, cpe, topo)
    payload = build_joint_path_evidence_dict(tp, cpe, topo, gate)
    assert payload["rule_case"] == "raisecom_overlay_conntrack_bidirectional"
    assert payload["l1_session"]["line_confirmed_count"] == 1
    assert payload["l1_session"]["sample_lines"]
