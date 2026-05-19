"""business_trace_evidence 与联合门控/拓扑着色融合单测。"""

from __future__ import annotations

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, InterfaceInfo
from sdwan_desktop.core.types.diagnosis import RootCause, Severity
from sdwan_desktop.interface.cli.commands.business_diagnose import _annotate_problem_nodes
from sdwan_desktop.services.diagnosis.business_trace_evidence import analyze_business_trace_evidence
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    compute_joint_overlay_datapath_gate,
)
from sdwan_desktop.services.reporter.joint_commercial_delivery import (
    failure_beyond_sdwan_edge_likely,
    joint_datapath_evidence_from_targeted_probe,
)
from sdwan_desktop.services.reporter.report_text_sanitize import sanitize_user_visible_text


def _tiktok_like_trace_hops() -> list[dict]:
    """与 business_joint_postfailure 报告样例一致的跳表片段。"""
    ips = [
        "10.10.100.1",
        "10.10.25.1",
        "8.1.3.1",
        "5.1.1.2",
        "61.8.196.147",
    ]
    return [
        {"hop": i + 1, "ip": ip, "rtts": [1.0, 1.0, 1.0]}
        for i, ip in enumerate(ips)
    ]


def _targeted_probe_envelope() -> dict:
    hops = _tiktok_like_trace_hops()
    return {
        "status": "partial",
        "data": {
            "business_probes": [
                {
                    "domain": "www.tiktok.com",
                    "port": 443,
                    "dns": {"status": "ok", "data": {"resolved_ips": ["31.13.92.37"]}},
                    "tcp": [
                        {
                            "host": "31.13.92.37",
                            "port": 443,
                            "status": "error",
                            "error": "[TOOL_TIMEOUT] 工具 tcping 执行超时 (10s) (trace_id: abc-def)",
                        }
                    ],
                    "trace": [
                        {
                            "host": "31.13.92.37",
                            "port": 443,
                            "status": "ok",
                            "data": {
                                "summary": {
                                    "target_reached": False,
                                    "total_hops": len(hops),
                                },
                                "hops": hops,
                            },
                        }
                    ],
                }
            ],
            "biz_target_ips": ["31.13.92.37"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 31.13.92.37": (
                    "ipv4 2 tcp 6 0 SYN_SENT src=10.10.25.3 dst=31.13.92.37 sport=1 dport=443 [UNREPLIED]"
                ),
            },
        },
        "error": None,
    }


def test_trace_evidence_egress_past_cpe() -> None:
    tp = _targeted_probe_envelope()
    topo = {
        "pc_node_id": "pc-001",
        "cpe_node_id": "cpe-001",
        "nodes": [
            {"id": "pc-001", "type": "pc", "ip_address": "10.10.100.161"},
            {"id": "cpe-001", "type": "cpe", "ip_address": "10.10.25.1"},
        ],
    }
    cpe = CpeConfiguration(
        vendor="raisecom",
        model="MSG5200B",
        interfaces=[InterfaceInfo(name="ge1", ip_address="192.168.20.20")],
    )
    ev = analyze_business_trace_evidence(tp, cpe, topo)
    assert ev.trace_available is True
    assert ev.egress_past_cpe is True
    assert ev.public_internet_after_cpe is True


def test_raisecom_gate_no_overlay_for_conntrack_plus_public_egress_only() -> None:
    """公网目的、无 vxlan 回程旁证：不展示 Overlay（已废除 D0 公网 DIP 硬否决）。"""
    tp = _targeted_probe_envelope()
    topo = {"cpe_node_id": "cpe-001", "pc_node_id": "pc-001", "nodes": []}
    cpe = CpeConfiguration(vendor="raisecom", model="MSG5200B")
    gate = compute_joint_overlay_datapath_gate(tp, cpe, topo)
    assert gate.show_overlay_tunnel_strip is False
    assert gate.rule_case == "raisecom_underlay_no_overlay_evidence"
    assert gate.evidence_tier == "underlay_only"


def test_failure_beyond_sdwan_edge_with_trace_and_conntrack() -> None:
    tp = _targeted_probe_envelope()
    joint_ev = joint_datapath_evidence_from_targeted_probe(tp)
    assert joint_ev is not None
    assert failure_beyond_sdwan_edge_likely(tp, joint_ev) is True


def test_annotate_suppresses_cpe_red_for_biz_tcp_when_beyond_edge() -> None:
    tp = _targeted_probe_envelope()
    topo = {
        "pc_node_id": "pc-001",
        "cpe_node_id": "cpe-001",
        "gateway_node_id": "gw-001",
        "hub_node_id": "hub-001",
        "nodes": [
            {"id": "pc-001", "type": "pc"},
            {"id": "cpe-001", "type": "cpe", "ip_address": "10.10.25.1"},
            {"id": "gw-001", "type": "gateway"},
            {"id": "hub-001", "type": "hub"},
        ],
        "edges": [
            {"source_id": "pc-001", "target_id": "cpe-001"},
            {"source_id": "cpe-001", "target_id": "hub-001"},
        ],
        "layout_underlay_items": [],
    }
    causes = [
        RootCause(
            cause_id="BIZ-TCP-TIMEOUT-001",
            title="业务 TCP 超时",
            description="test",
            severity=Severity.ERROR,
            confidence=0.7,
            evidence_refs=[],
            matched_rules=[],
        )
    ]
    cpe = CpeConfiguration(vendor="raisecom", model="MSG5200B")
    _annotate_problem_nodes(topo, causes, tp, cpe_configuration=cpe)
    assert "cpe-001" not in topo.get("problem_node_ids", [])
    assert topo.get("business_trace_evidence", {}).get("egress_past_cpe") is True


def test_sanitize_strips_trace_id_from_user_text() -> None:
    raw = "[TOOL_TIMEOUT] 超时 (trace_id: 142af8b1-6c8b-45d9-9b3a-fbc3a8b195de)"
    out = sanitize_user_visible_text(raw)
    assert "trace_id" not in out.lower()
    assert "TOOL_TIMEOUT" in out
