"""联合报告拓扑展示剖面：与 gate / trace / 隧道边一致。"""

from __future__ import annotations

from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import JointOverlayDatapathGate
from sdwan_desktop.services.reporter.topology_joint_presentation import (
    resolve_joint_topology_presentation,
)


def test_sdwan_profile_when_gate_requests_overlay_strip() -> None:
    gate = JointOverlayDatapathGate(
        show_overlay_tunnel_strip=True,
        overlay_evidence_positive=True,
        rule_case="raisecom_session_matched_policy_prefix",
        datapath_banner="",
        joint_overlay_topology_note="",
    )
    topo = {
        "cpe_node_id": "cpe-001",
        "hub_node_id": "hub-001",
        "pc_node_id": "pc-001",
        "nodes": [{"id": "pc-001", "type": "pc", "ip_address": "10.10.100.161"}],
        "edges": [
            {
                "link_type": "tunnel",
                "source_id": "cpe-001",
                "target_id": "hub-001",
            }
        ],
    }
    tp = {
        "status": "ok",
        "data": {
            "biz_target_ips": ["31.13.92.37"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 31.13.92.37": "tcp src=10.10.25.1 dst=31.13.92.37",
            },
            "business_probes": [
                {
                    "trace": [
                        {
                            "status": "ok",
                            "data": {
                                "hops": [
                                    {"hop": 1, "ip": "10.10.25.1"},
                                    {"hop": 2, "ip": "203.0.113.1"},
                                    {"hop": 10, "ip": "157.240.85.210"},
                                ],
                                "summary": {"target_reached": False},
                            },
                        }
                    ],
                }
            ],
        },
    }
    pres = resolve_joint_topology_presentation(
        topology_dict=topo,
        targeted_probe=tp,
        gate=gate,
    )
    assert pres.variant == "sdwan"
    assert pres.show_overlay_tunnel_strip is True
    assert pres.path_focus_beyond_sdwan is False


def test_internet_profile_without_tunnel_or_overlay_evidence() -> None:
    gate = JointOverlayDatapathGate(
        show_overlay_tunnel_strip=False,
        overlay_evidence_positive=False,
        rule_case="non_raisecom_no_conntrack",
        datapath_banner="",
        joint_overlay_topology_note="",
    )
    pres = resolve_joint_topology_presentation(
        topology_dict={"edges": [], "nodes": []},
        targeted_probe={"status": "ok", "data": {"business_probes": [], "raw_outputs": {}}},
        gate=gate,
    )
    assert pres.variant == "internet"
    assert pres.show_overlay_tunnel_strip is False


def test_baidu_like_probe_ok_no_overlay_when_gate_off() -> None:
    """公网业务探测成功 + conntrack 命中 + gate 未绑定 Overlay → internet 剖面、无隧道条带。"""
    gate = JointOverlayDatapathGate(
        show_overlay_tunnel_strip=False,
        overlay_evidence_positive=False,
        rule_case="raisecom_heuristic_uncertain_no_overlay_strip",
        datapath_banner="",
        joint_overlay_topology_note="",
    )
    topo = {
        "cpe_node_id": "cpe-001",
        "hub_node_id": "hub-001",
        "pc_node_id": "pc-001",
        "nodes": [{"id": "pc-001", "type": "pc", "ip_address": "10.10.100.161"}],
        "edges": [
            {"link_type": "tunnel", "source_id": "cpe-001", "target_id": "hub-001"},
        ],
    }
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [
                {
                    "domain": "www.baidu.com",
                    "port": 443,
                    "dns": {"status": "ok", "data": {"resolved_ips": ["220.181.111.232"]}},
                    "tcp": [
                        {
                            "host": "220.181.111.232",
                            "port": 443,
                            "status": "ok",
                            "data": {"port_open": True},
                        }
                    ],
                    "trace": [],
                }
            ],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 220.181.111.232": (
                    "tcp src=10.10.100.161 dst=220.181.111.232"
                ),
            },
        },
    }
    pres = resolve_joint_topology_presentation(
        topology_dict=topo,
        targeted_probe=tp,
        gate=gate,
    )
    assert pres.variant == "internet"
    assert pres.show_overlay_tunnel_strip is False


def test_verify_ok_path_beyond_suppresses_fault_narrative() -> None:
    """本机探测全通 + conntrack + 已出 CPE：仍 path_beyond 抑制标红，但不启用公网故障 ingress。"""
    gate = JointOverlayDatapathGate(
        show_overlay_tunnel_strip=False,
        overlay_evidence_positive=False,
        rule_case="raisecom_heuristic_uncertain_no_overlay_strip",
        datapath_banner="",
        joint_overlay_topology_note="",
    )
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [
                {
                    "domain": "www.youtube.com",
                    "port": 443,
                    "dns": {"status": "ok", "data": {"resolved_ips": ["172.253.118.136"]}},
                    "tcp": [
                        {
                            "host": "172.253.118.136",
                            "port": 443,
                            "status": "ok",
                            "data": {"port_open": True},
                        }
                    ],
                    "trace": [
                        {
                            "status": "ok",
                            "data": {
                                "hops": [
                                    {"hop": 1, "ip": "10.10.25.1"},
                                    {"hop": 2, "ip": "8.1.3.1"},
                                ],
                                "summary": {"target_reached": False},
                            },
                        }
                    ],
                }
            ],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 172.253.118.136": (
                    "ipv4 2 icmp 1 0 src=10.10.25.3 dst=172.253.118.136 [UNREPLIED]\n"
                    "ipv4 2 tcp 6 0 TIME_WAIT src=10.10.25.3 dst=172.253.118.136 dport=443"
                ),
            },
        },
    }
    pres = resolve_joint_topology_presentation(
        topology_dict={"cpe_node_id": "cpe-001", "hub_node_id": "hub-001", "edges": []},
        targeted_probe=tp,
        gate=gate,
        business_probe_all_ok=True,
    )
    assert pres.path_focus_beyond_sdwan is True
    assert pres.underlay_fault_on_internet_ingress is False
    assert "故障段示意" not in pres.narrative_coherence_note
    assert "本机探测已通过" in pres.narrative_coherence_note
