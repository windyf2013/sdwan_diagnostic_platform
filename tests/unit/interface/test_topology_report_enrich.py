"""深度报告：拓扑字典富化（Underlay 不含隧道 Hub；Overlay 仍含 Hub 与 hop 样式）。"""

from sdwan_desktop.interface.cli.commands.deep_dive import _enrich_topology_report_dict


def test_enrich_underlay_excludes_tunnel_hub_underlay_chain_keeps_overlay_hub():
    """存在 CPE↔Hub 隧道时：Underlay 不画隧道对端 Hub；Hub 仍出现在 Overlay 元数据与节点 iface 富化中。"""
    topo = {
        "nodes": [
            {"id": "pc-001", "type": "pc", "name": "pc", "metadata": {}},
            {"id": "cpe-001", "type": "cpe", "name": "cpe", "metadata": {}},
            {"id": "gw-001", "type": "gateway", "name": "gw", "metadata": {}},
            {"id": "hub-001", "type": "hub", "name": "hub", "metadata": {}},
        ],
        "edges": [
            {
                "link_type": "physical",
                "source_id": "pc-001",
                "target_id": "cpe-001",
                "source_interface": "10.0.0.2",
                "target_interface": "10.0.0.1",
                "metadata": {"source_interface_name": "eth0", "target_interface_name": "lan1"},
            },
            {
                "link_type": "logical",
                "source_id": "cpe-001",
                "target_id": "gw-001",
                "source_interface": "192.168.1.10",
                "target_interface": "192.168.1.1",
                "metadata": {
                    "source_interface_name": "wan0",
                    "target_interface_name": "gw",
                    "adjacency_evidence": "route_only",
                },
            },
            {
                "link_type": "tunnel",
                "source_id": "cpe-001",
                "target_id": "hub-001",
                "source_interface": "8.0.0.2",
                "target_interface": "5.0.0.1",
                "metadata": {
                    "overlay_local_iface": "vx1",
                    "overlay_local_ip": "8.0.0.2",
                    "overlay_segment_peer_ip": "8.0.0.1",
                    "overlay_tunnel_peer_ip": "5.0.0.1",
                    "underlay_wan_ip": "192.168.1.10",
                    "underlay_wan_iface": "wan0",
                    "underlay_next_hop_ip": "192.168.1.1",
                },
            },
        ],
        "pc_node_id": "pc-001",
        "cpe_node_id": "cpe-001",
        "gateway_node_id": "gw-001",
        "hub_node_id": "hub-001",
    }
    _enrich_topology_report_dict(topo)
    ids = [x["node"]["id"] for x in topo["layout_underlay_items"] if x["kind"] == "node"]
    assert ids == ["pc-001", "cpe-001", "gw-001"]
    hops = [x for x in topo["layout_underlay_items"] if x["kind"] == "hop"]
    assert [h["connection"] for h in hops] == ["direct", "indirect"]
    hub = next(n for n in topo["nodes"] if n["id"] == "hub-001")
    assert hub["metadata"]["downlink_interfaces"][0]["ip"] == "192.168.1.10"
    lo = topo["layout_overlay"]
    assert lo["overlay_outer_encap_same_slash24"] is False
    assert lo["overlay_underlay_next_hop_ip"] == "192.168.1.1"
    assert lo["hub_encap_row_label"] == "对端隧道目的"


def test_enrich_outer_encap_same_slash24_labels():
    topo = {
        "nodes": [
            {"id": "cpe-001", "type": "cpe", "name": "cpe", "metadata": {}},
            {"id": "hub-001", "type": "hub", "name": "hub", "ip_address": "10.10.10.20", "metadata": {}},
        ],
        "edges": [
            {
                "link_type": "tunnel",
                "source_id": "cpe-001",
                "target_id": "hub-001",
                "source_interface": "8.0.0.2",
                "target_interface": "10.10.10.20",
                "metadata": {
                    "overlay_local_ip": "8.0.0.2",
                    "overlay_tunnel_peer_ip": "10.10.10.20",
                    "underlay_wan_ip": "10.10.10.10",
                    "underlay_wan_iface": "ge0",
                    "underlay_next_hop_ip": "10.10.10.20",
                },
            },
        ],
        "cpe_node_id": "cpe-001",
        "hub_node_id": "hub-001",
        "pc_node_id": None,
        "gateway_node_id": None,
    }
    _enrich_topology_report_dict(topo)
    lo = topo["layout_overlay"]
    assert lo["overlay_outer_encap_same_slash24"] is True
    assert lo["cpe_encap_row_label"] == "封装地址"
    assert lo["hub_encap_row_label"] == "封装地址"
    assert not lo.get("overlay_encap_note")
