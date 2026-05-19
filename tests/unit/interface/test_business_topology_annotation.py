"""business_diagnose：拓扑问题高亮与隧道 ICMP / conntrack 证据对齐。"""

from __future__ import annotations

from sdwan_desktop.core.types.diagnosis import RootCause, Severity
from sdwan_desktop.interface.cli.commands.business_diagnose import _annotate_problem_nodes


def test_annotate_suppresses_overlay_and_cpe_when_path_beyond_tunnel() -> None:
    """peer ICMP 全通 + 业务目的 IP 上 SYN-only 时，不标 Overlay 隧道故障、不标 CPE 策略为 underlay 红段。"""
    topo: dict = {
        "nodes": [
            {"id": "pc", "type": "pc"},
            {"id": "cpe", "type": "cpe"},
            {"id": "hub", "type": "hub"},
        ],
        "edges": [
            {"source_id": "pc", "target_id": "cpe"},
            {"source_id": "cpe", "target_id": "hub"},
        ],
        "pc_node_id": "pc",
        "cpe_node_id": "cpe",
        "hub_node_id": "hub",
        "gateway_node_id": None,
        "layout_underlay_items": [],
    }
    causes = [
        RootCause(
            cause_id="CPE-002-WARN",
            title="Overlay 未知",
            description="d",
            severity=Severity.WARNING,
            confidence=0.6,
        ),
        RootCause(
            cause_id="CPE-003",
            title="策略未命中",
            description="d",
            severity=Severity.ERROR,
            confidence=0.8,
        ),
        RootCause(
            cause_id="BIZ-TCP-001",
            title="TCP 超时",
            description="d",
            severity=Severity.ERROR,
            confidence=0.7,
        ),
    ]
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "x.example", "port": 443}],
            "biz_target_ips": ["8.8.8.8"],
            "raw_outputs": {
                "diagnose:ping tunnel_peer 10.0.0.1": (
                    "2 packets transmitted, 2 received, 0% packet loss"
                ),
                "diagnose:nf_conntrack grep 8.8.8.8": (
                    "tcp SYN_SENT src=192.168.1.2 dst=8.8.8.8 sport=12345 dport=443 [UNREPLIED]"
                ),
            },
        },
    }
    _annotate_problem_nodes(topo, causes, tp)
    assert topo.get("overlay_problem") is None
    node_ids = {m["node_id"] for m in topo.get("problem_markers", [])}
    assert "cpe" not in node_ids
    assert "hub" not in node_ids
    assert topo.get("business_fault_beyond_tunnel_edge") is True
    layers = {m["layer"] for m in topo.get("problem_edge_markers", [])}
    assert "overlay" not in layers
    assert "cpe" not in layers or topo.get("business_fault_beyond_tunnel_edge")


def test_annotate_suppresses_heuristic_cpe_when_targeted_business_ok() -> None:
    """业务探测行已全部成功时，不因 CPE-003 等启发式在 Underlay 标 PC↔CPE 故障段。"""
    topo: dict = {
        "nodes": [
            {"id": "pc", "type": "pc"},
            {"id": "cpe", "type": "cpe"},
            {"id": "hub", "type": "hub"},
        ],
        "edges": [
            {"source_id": "pc", "target_id": "cpe", "problem": True},
            {"source_id": "cpe", "target_id": "hub"},
        ],
        "pc_node_id": "pc",
        "cpe_node_id": "cpe",
        "hub_node_id": "hub",
        "gateway_node_id": None,
        "layout_underlay_items": [{"kind": "hop", "edge_key": "pc->cpe", "problem": True}],
    }
    causes = [
        RootCause(
            cause_id="CPE-003",
            title="策略路由未生效",
            description="d",
            severity=Severity.ERROR,
            confidence=0.8,
        ),
    ]
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [
                {
                    "domain": "x.example",
                    "port": 443,
                    "dns": {"status": "ok", "data": {}, "error": None},
                    "tcp": [
                        {
                            "host": "8.8.8.8",
                            "port": 443,
                            "status": "ok",
                            "data": {"port_open": True},
                        }
                    ],
                }
            ],
        },
    }
    _annotate_problem_nodes(topo, causes, tp)
    assert topo.get("problem_markers") == []
    assert topo.get("overlay_problem") is None
    assert topo["edges"][0].get("problem") is None


def test_annotate_keeps_infra_markers_when_targeted_business_ok() -> None:
    """业务 path ok 时仍保留 CPE-001 / 链路等基础设施类根因的拓扑标记（非整表清空）。"""
    topo: dict = {
        "nodes": [
            {"id": "pc", "type": "pc"},
            {"id": "cpe", "type": "cpe"},
            {"id": "hub", "type": "hub"},
        ],
        "edges": [
            {"source_id": "pc", "target_id": "cpe"},
            {"source_id": "cpe", "target_id": "hub"},
        ],
        "pc_node_id": "pc",
        "cpe_node_id": "cpe",
        "hub_node_id": "hub",
        "gateway_node_id": None,
        "layout_underlay_items": [],
    }
    causes = [
        RootCause(
            cause_id="RAISECOM-LINK-PROT-001",
            title="链路保护 Down",
            description="d",
            severity=Severity.WARNING,
            confidence=0.72,
        ),
        RootCause(
            cause_id="CPE-003",
            title="策略路由未生效",
            description="d",
            severity=Severity.ERROR,
            confidence=0.8,
        ),
    ]
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [
                {
                    "domain": "x.example",
                    "port": 443,
                    "dns": {"status": "ok", "data": {}, "error": None},
                    "tcp": [
                        {
                            "host": "8.8.8.8",
                            "port": 443,
                            "status": "ok",
                            "data": {"port_open": True},
                        }
                    ],
                }
            ],
        },
    }
    _annotate_problem_nodes(topo, causes, tp)
    node_ids = {m["node_id"] for m in topo.get("problem_markers", [])}
    assert "cpe" in node_ids
    reasons = {m["reason"] for m in topo.get("problem_markers", [])}
    assert "链路保护 Down" in reasons
    assert not any("策略" in m["reason"] for m in topo.get("problem_markers", []))


def test_annotate_keeps_overlay_when_no_path_beyond_evidence() -> None:
    topo: dict = {
        "nodes": [
            {"id": "pc", "type": "pc"},
            {"id": "cpe", "type": "cpe"},
            {"id": "hub", "type": "hub"},
        ],
        "edges": [
            {"source_id": "pc", "target_id": "cpe"},
            {"source_id": "cpe", "target_id": "hub", "link_type": "tunnel"},
        ],
        "pc_node_id": "pc",
        "cpe_node_id": "cpe",
        "hub_node_id": "hub",
        "gateway_node_id": None,
        "layout_underlay_items": [
            {"kind": "node", "node": {"id": "pc", "type": "pc"}},
            {
                "kind": "hop",
                "edge_key": "pc->cpe",
                "source_id": "pc",
                "target_id": "cpe",
                "connection": "indirect",
            },
            {"kind": "node", "node": {"id": "cpe", "type": "cpe"}},
            {
                "kind": "hop",
                "edge_key": "cpe->hub",
                "source_id": "cpe",
                "target_id": "hub",
                "connection": "indirect",
            },
            {"kind": "node", "node": {"id": "hub", "type": "hub"}},
        ],
    }
    causes = [
        RootCause(
            cause_id="CPE-002-WARN",
            title="Overlay 未知",
            description="d",
            severity=Severity.WARNING,
            confidence=0.6,
        ),
    ]
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "x.example"}],
            "biz_target_ips": ["8.8.8.8"],
            "raw_outputs": {},
        },
    }
    _annotate_problem_nodes(topo, causes, tp)
    assert topo.get("overlay_problem") is not None
    for it in topo.get("layout_underlay_items") or []:
        if isinstance(it, dict) and it.get("kind") == "hop":
            assert it.get("problem") is not True


def test_finalize_joint_appends_internet_terminal_sdwan() -> None:
    from sdwan_desktop.interface.cli.commands.business_diagnose import finalize_business_topology_joint_report
    from sdwan_desktop.services.reporter.topology_joint_presentation import (
        JointTopologyPresentation,
    )

    pres = JointTopologyPresentation(
        variant="sdwan",
        show_overlay_tunnel_strip=True,
        path_focus_beyond_sdwan=True,
        trim_underlay_at_first_problem_node=False,
        underlay_fault_on_internet_ingress=True,
        suppress_heuristic_cpe_underlay_markers=True,
        narrative_coherence_note="",
    )
    topo: dict = {
        "nodes": [],
        "edges": [
            {"link_type": "tunnel", "source_id": "cpe", "target_id": "hub"},
        ],
        "pc_node_id": "pc",
        "cpe_node_id": "cpe",
        "hub_node_id": "hub",
        "gateway_node_id": "gw",
        "layout_underlay_items": [
            {"kind": "node", "node": {"id": "pc", "type": "pc"}},
            {"kind": "hop", "edge_key": "pc->cpe", "source_id": "pc", "target_id": "cpe", "connection": "indirect"},
            {"kind": "node", "node": {"id": "cpe", "type": "cpe"}},
            {"kind": "hop", "edge_key": "cpe->gw", "source_id": "cpe", "target_id": "gw", "connection": "indirect"},
            {"kind": "node", "node": {"id": "gw", "type": "gateway"}},
        ],
        "business_failure_stage": {"stage": "tcp_connect"},
        "problem_node_ids": [],
        "business_fault_beyond_tunnel_edge": True,
    }
    finalize_business_topology_joint_report(topo, pres)
    assert topo.get("topology_display_variant") == "sdwan"
    ids = [x["node"]["id"] for x in topo["layout_underlay_items"] if x.get("kind") == "node"]
    assert ids[-1] == "internet-terminal"
    tail_hops = [x for x in topo["layout_underlay_items"] if x.get("kind") == "hop"]
    assert tail_hops[-1].get("edge_key", "").endswith("->internet-terminal")
    assert tail_hops[-1].get("problem") is True
    assert "internet-terminal" in topo.get("topology_underlay_problem_node_ids", [])


def test_annotate_heuristic_cpe_suppressed_when_presentation_says_so() -> None:
    from sdwan_desktop.services.reporter.topology_joint_presentation import (
        JointTopologyPresentation,
    )

    pres = JointTopologyPresentation(
        variant="sdwan",
        show_overlay_tunnel_strip=True,
        path_focus_beyond_sdwan=True,
        trim_underlay_at_first_problem_node=False,
        underlay_fault_on_internet_ingress=True,
        suppress_heuristic_cpe_underlay_markers=True,
        narrative_coherence_note="",
    )
    topo: dict = {
        "nodes": [
            {"id": "pc", "type": "pc"},
            {"id": "cpe", "type": "cpe"},
        ],
        "edges": [{"source_id": "pc", "target_id": "cpe"}],
        "pc_node_id": "pc",
        "cpe_node_id": "cpe",
        "hub_node_id": None,
        "gateway_node_id": None,
        "layout_underlay_items": [],
    }
    causes = [
        RootCause(
            cause_id="CPE-003",
            title="策略未命中",
            description="d",
            severity=Severity.WARNING,
            confidence=0.7,
        ),
        RootCause(
            cause_id="CPE-004",
            title="NAT 未覆盖",
            description="d",
            severity=Severity.WARNING,
            confidence=0.7,
        ),
    ]
    tp = {"status": "ok", "data": {"business_probes": [{"domain": "x.example"}]}}
    _annotate_problem_nodes(topo, causes, tp, presentation=pres)
    assert topo.get("problem_markers") == []
    assert topo.get("business_fault_beyond_tunnel_edge") is False


def test_finalize_internet_variant_suppresses_overlay() -> None:
    from sdwan_desktop.interface.cli.commands.business_diagnose import finalize_business_topology_joint_report
    from sdwan_desktop.services.reporter.topology_joint_presentation import (
        JointTopologyPresentation,
    )

    pres = JointTopologyPresentation(
        variant="internet",
        show_overlay_tunnel_strip=False,
        path_focus_beyond_sdwan=False,
        trim_underlay_at_first_problem_node=True,
        underlay_fault_on_internet_ingress=False,
        suppress_heuristic_cpe_underlay_markers=False,
        narrative_coherence_note="互联网直连",
    )
    topo: dict = {
        "nodes": [],
        "edges": [],
        "pc_node_id": "pc",
        "cpe_node_id": "cpe",
        "hub_node_id": None,
        "gateway_node_id": None,
        "layout_underlay_items": [
            {"kind": "node", "node": {"id": "pc", "type": "pc"}},
            {"kind": "hop", "edge_key": "pc->cpe", "source_id": "pc", "target_id": "cpe", "connection": "indirect"},
            {"kind": "node", "node": {"id": "cpe", "type": "cpe"}},
        ],
        "business_failure_stage": {"stage": "ok"},
        "problem_node_ids": [],
    }
    finalize_business_topology_joint_report(topo, pres)
    assert topo.get("topology_display_variant") == "internet"
    assert topo.get("business_joint_suppress_overlay_topology_presentation") is True


def test_reconcile_datapath_when_gate_shows_tunnel_but_presentation_hides() -> None:
    """探测全通 + 剖面强制不画 Overlay 时，覆写 gate 的「将展示隧道」类横幅，避免文案与模板矛盾。"""
    from sdwan_desktop.interface.cli.commands.business_diagnose import (
        _reconcile_joint_datapath_reading_layer,
    )
    from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import JointOverlayDatapathGate
    from sdwan_desktop.services.reporter.topology_joint_presentation import (
        JointTopologyPresentation,
    )

    gate = JointOverlayDatapathGate(
        show_overlay_tunnel_strip=True,
        overlay_evidence_positive=True,
        rule_case="non_raisecom_conntrack_hits",
        datapath_banner="【旧】将展示隧道示意条",
        joint_overlay_topology_note="旧 overlay 脚注",
    )
    pres = JointTopologyPresentation(
        variant="internet",
        show_overlay_tunnel_strip=False,
        path_focus_beyond_sdwan=False,
        trim_underlay_at_first_problem_node=True,
        underlay_fault_on_internet_ingress=False,
        suppress_heuristic_cpe_underlay_markers=True,
        narrative_coherence_note="",
    )
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [
                {
                    "domain": "ok.example",
                    "port": 443,
                    "dns": {"status": "ok", "data": {"resolved_ips": ["1.1.1.1"]}},
                    "tcp": [
                        {
                            "host": "1.1.1.1",
                            "port": 443,
                            "status": "ok",
                            "data": {"port_open": True},
                        }
                    ],
                    "trace": [],
                }
            ],
        },
    }
    topo: dict = {
        "declared_business_datapath_banner": gate.datapath_banner,
        "joint_overlay_topology_note": gate.joint_overlay_topology_note,
        "joint_overlay_suppress_reason": "",
        "declared_business_datapath_verdict": "overlay_evidence_positive",
        "joint_overlay_rule_case": gate.rule_case,
    }
    _reconcile_joint_datapath_reading_layer(topo, gate, pres, tp)
    assert "互联网核查剖面" in (topo.get("declared_business_datapath_banner") or "")
    assert topo.get("joint_overlay_topology_note") == ""
    assert "topology_joint_presentation" in (topo.get("joint_overlay_suppress_reason") or "")
    assert topo.get("declared_business_datapath_verdict") == "unverified"
    assert topo.get("business_joint_suppress_overlay_topology_presentation") is True
