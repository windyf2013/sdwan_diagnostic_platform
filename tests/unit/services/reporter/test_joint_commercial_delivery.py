"""Tests for joint_commercial_delivery (商用交付摘要载荷)."""

from __future__ import annotations

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity
from sdwan_desktop.services.reporter.joint_commercial_delivery import (
    CommercialDeliveryPayload,
    _conntrack_blob_has_src_ipv4,
    _has_syn_only_conntrack,
    _summarize_ping_output,
    build_commercial_delivery_payload,
    business_joint_should_present_overlay_tunnel_narrative,
    joint_datapath_evidence_from_targeted_probe,
    path_beyond_tunnel_likely,
)


def test_build_returns_none_without_targeted_probe() -> None:
    d = DiagnosisResult(diagnosis_type="deep_dive", root_causes=[])
    assert (
        build_commercial_delivery_payload(
            trace_id="t-1",
            diagnosis=d,
            topology_dict={},
            targeted_probe=None,
        )
        is None
    )


def test_build_returns_none_when_status_not_ok() -> None:
    d = DiagnosisResult(diagnosis_type="deep_dive", root_causes=[])
    tp = {
        "status": "failed",
        "data": {
            "business_probes": [{"domain": "x.example"}],
            "raw_outputs": {},
        },
    }
    assert (
        build_commercial_delivery_payload(
            trace_id="t-1",
            diagnosis=d,
            topology_dict={},
            targeted_probe=tp,
        )
        is None
    )


def test_summarize_ping_ok_and_fail() -> None:
    ok_raw = "2 packets transmitted, 2 received, 0% packet loss, time 1ms"
    st, _ = _summarize_ping_output(ok_raw)
    assert st == "ok"

    fail_raw = "2 packets transmitted, 0 received, 100% packet loss"
    st2, _ = _summarize_ping_output(fail_raw)
    assert st2 == "fail"


def test_build_payload_tunnel_ok_syn_only_conntrack() -> None:
    """隧道 peer ICMP 正常 + conntrack 仅 SYN → 主叙述收敛到对端以远。"""
    causes = [
        RootCause(
            cause_id="CPE-003",
            title="t",
            description="d",
            severity=Severity.WARNING,
            confidence=0.5,
        )
    ]
    d = DiagnosisResult(diagnosis_type="deep_dive", root_causes=causes)
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "svc.example", "port": 443}],
            "biz_target_ips": ["203.0.113.10"],
            "raw_outputs": {
                "diagnose:ping tunnel_peer 198.51.100.2": (
                    "2 packets transmitted, 2 received, 0% packet loss, time 2ms"
                ),
                "diagnose:nf_conntrack grep 203.0.113.10": (
                    "ipv4 2 tcp 6 120 SYN_SENT src=10.1.1.5 dst=203.0.113.10 sport=54321 "
                    "dport=443 [UNREPLIED] src=203.0.113.10 dst=10.1.1.5 sport=443 dport=54321"
                ),
            },
        },
    }
    topo = {
        "pc_snapshot_included": True,
        "pc_node_id": "pc-1",
        "nodes": [{"id": "pc-1", "type": "pc", "ip_address": "10.1.1.99"}],
    }
    payload = build_commercial_delivery_payload(
        trace_id="trace-x",
        diagnosis=d,
        topology_dict=topo,
        targeted_probe=tp,
    )
    assert isinstance(payload, CommercialDeliveryPayload)
    assert "隧道对端网络层可达" in payload.headline
    assert "SYN" in payload.headline
    assert len(payload.tunnel_peer_probes) == 1
    assert payload.tunnel_peer_probes[0]["peer_ip"] == "198.51.100.2"
    assert payload.tunnel_peer_probes[0]["status"] == "ok"
    dct = payload.as_template_dict()
    assert dct["trace_id"] == "trace-x"
    assert any(row["id"] == "T1" for row in dct["checklist"])
    # PC IP != conntrack src → notice
    assert any("10.1.1.99" in n for n in dct["notices"])


def test_build_payload_ping_fail_prioritizes_tunnel() -> None:
    d = DiagnosisResult(diagnosis_type="deep_dive", root_causes=[])
    tp = {
        "status": "partial",
        "data": {
            "business_probes": [{"domain": "svc.example"}],
            "biz_target_ips": ["203.0.113.10"],
            "raw_outputs": {
                "diagnose:ping tunnel_peer 198.51.100.2": (
                    "2 packets transmitted, 0 received, 100% packet loss"
                ),
            },
        },
    }
    payload = build_commercial_delivery_payload(
        trace_id="t2",
        diagnosis=d,
        topology_dict={"pc_snapshot_included": False},
        targeted_probe=tp,
    )
    assert payload is not None
    assert "隧道对端 ICMP" in payload.headline
    assert payload.tunnel_peer_probes[0]["status"] == "fail"


def test_path_beyond_tunnel_likely_requires_ping_ok_and_syn_conntrack() -> None:
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "x.example"}],
            "biz_target_ips": ["8.8.8.8"],
            "raw_outputs": {
                "diagnose:ping tunnel_peer 10.0.0.1": (
                    "2 packets transmitted, 2 received, 0% packet loss"
                ),
                "diagnose:nf_conntrack grep 8.8.8.8": "tcp SYN_SENT src=192.168.1.2 dst=8.8.8.8",
            },
        },
    }
    ev = joint_datapath_evidence_from_targeted_probe(tp)
    assert ev is not None
    assert path_beyond_tunnel_likely(ev) is True


def test_path_beyond_tunnel_not_likely_when_no_tunnel_probe() -> None:
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "x.example"}],
            "biz_target_ips": ["8.8.8.8"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 8.8.8.8": "tcp SYN_SENT src=192.168.1.2 dst=8.8.8.8",
            },
        },
    }
    ev = joint_datapath_evidence_from_targeted_probe(tp)
    assert ev is not None
    assert path_beyond_tunnel_likely(ev) is False


def test_business_joint_should_present_overlay_false_when_conntrack_grep_empty() -> None:
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "www.baidu.com", "port": 443, "dns": {"status": "ok"}}],
            "biz_target_ips": ["198.51.100.1"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 198.51.100.1": "",
            },
        },
    }
    assert business_joint_should_present_overlay_tunnel_narrative(tp) is False


def test_business_joint_should_present_overlay_true_when_conntrack_has_lines() -> None:
    """5200B：会话 DIP 为隧道下一跳时启用 Overlay（非仅公网 DIP）。"""
    from sdwan_desktop.core.types.cpe_config import CpeConfiguration

    cpe = CpeConfiguration(vendor="raisecom", model="MSG5200B", version="1", hostname="cpe1")
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "svc.example", "port": 443, "dns": {"status": "ok"}}],
            "biz_target_ips": ["203.0.113.10"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 203.0.113.10": (
                    "tcp SYN_SENT src=10.1.1.5 dst=5.96.1.26 sport=54321 dport=443 "
                    "oifname=vxlan2500110 [UNREPLIED]"
                ),
            },
        },
    }
    assert business_joint_should_present_overlay_tunnel_narrative(tp, cpe) is True


def test_business_joint_should_present_overlay_false_when_only_public_dip() -> None:
    """5200B D0：仅公网 Underlay DIP 时不展示 Overlay。"""
    from sdwan_desktop.core.types.cpe_config import CpeConfiguration

    cpe = CpeConfiguration(vendor="raisecom", model="MSG5200B", version="1", hostname="cpe1")
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "svc.example", "port": 443, "dns": {"status": "ok"}}],
            "biz_target_ips": ["203.0.113.10"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 203.0.113.10": (
                    "ipv4 2 tcp 6 120 SYN_SENT src=10.1.1.5 dst=203.0.113.10 sport=54321 "
                    "dport=443 [UNREPLIED] src=203.0.113.10 dst=10.1.1.5 sport=443 dport=54321"
                ),
            },
        },
    }
    assert business_joint_should_present_overlay_tunnel_narrative(tp, cpe) is False


def test_business_joint_should_present_overlay_false_when_partial_biz_and_empty_conntrack() -> None:
    tp = {
        "status": "partial",
        "data": {
            "business_probes": [{"domain": "svc.example", "port": 443, "dns": {"status": "error"}}],
            "biz_target_ips": ["203.0.113.10"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 203.0.113.10": "",
            },
        },
    }
    assert business_joint_should_present_overlay_tunnel_narrative(tp) is False


def test_build_payload_underlay_focus_strips_tunnel_peer_block() -> None:
    d = DiagnosisResult(diagnosis_type="business_diagnose", root_causes=[])
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "www.baidu.com", "port": 443, "dns": {"status": "ok"}}],
            "biz_target_ips": ["198.51.100.9"],
            "raw_outputs": {
                "diagnose:ping tunnel_peer 198.51.100.2": (
                    "2 packets transmitted, 2 received, 0% packet loss, time 2ms"
                ),
            },
        },
    }
    payload = build_commercial_delivery_payload(
        trace_id="t-ul",
        diagnosis=d,
        topology_dict={"pc_snapshot_included": True},
        targeted_probe=tp,
        underlay_declared_business_focus=True,
    )
    assert payload is not None
    assert len(payload.tunnel_peer_probes) == 0
    assert "Overlay/隧道域" in payload.headline
    assert not any(row.get("id") == "T2" for row in payload.checklist)


def test_conntrack_blob_has_src_ipv4() -> None:
    blob = "tcp src=192.168.1.10 dst=8.8.8.8"
    assert _conntrack_blob_has_src_ipv4(blob, "192.168.1.10") is True
    assert _conntrack_blob_has_src_ipv4(blob, "192.168.1.1") is False


def test_build_payload_biz_ok_pc_src_absent_emits_upstream_nat_info() -> None:
    """本机探测全成功 + conntrack 有命中但无 PC 主地址为 src → INFO 路径解读（非严格证明 NAT）。"""
    d = DiagnosisResult(diagnosis_type="deep_dive", root_causes=[])
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [
                {
                    "domain": "svc.example",
                    "port": 443,
                    "dns": {"status": "ok", "data": {"resolved_ips": ["203.0.113.1"]}},
                    "tcp": [
                        {
                            "status": "ok",
                            "host": "203.0.113.1",
                            "data": {"port_open": True},
                        }
                    ],
                }
            ],
            "biz_target_ips": ["203.0.113.1"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 203.0.113.1": (
                    "ipv4 2 tcp 6 431999 ESTABLISHED src=10.88.0.1 dst=203.0.113.1 sport=44444 "
                    "dport=443 src=203.0.113.1 dst=10.88.0.1 sport=443 dport=44444"
                ),
            },
        },
    }
    topo = {
        "pc_snapshot_included": True,
        "pc_node_id": "pc-1",
        "nodes": [{"id": "pc-1", "type": "pc", "ip_address": "192.168.50.77"}],
    }
    payload = build_commercial_delivery_payload(
        trace_id="t-nat-hint",
        diagnosis=d,
        topology_dict=topo,
        targeted_probe=tp,
    )
    assert payload is not None
    notices = payload.as_template_dict()["notices"]
    assert any("【INFO · 路径解读】" in str(n) for n in notices)
    assert any("不能严格证明" in str(n) for n in notices)
    assert any("192.168.50.77" in str(n) for n in notices)


def test_has_syn_only_ignores_icmp_unreplied_when_tcp_time_wait() -> None:
    """ICMP [UNREPLIED] 不得单独触发 SYN-only；TIME_WAIT 视为已建立/已结束。"""
    blob = (
        "ipv4 2 icmp 1 0 src=10.10.25.3 dst=172.253.118.136 type=8 [UNREPLIED]\n"
        "ipv4 2 tcp 6 0 TIME_WAIT src=10.10.25.3 dst=172.253.118.136 sport=51427 dport=443\n"
    )
    assert _has_syn_only_conntrack(blob) is False


def test_has_syn_only_true_for_tcp_syn_sent_unreplied() -> None:
    blob = (
        "ipv4 2 tcp 6 120 SYN_SENT src=10.1.1.5 dst=203.0.113.10 sport=54321 "
        "dport=443 [UNREPLIED] src=203.0.113.10 dst=10.1.1.5 sport=443 dport=54321"
    )
    assert _has_syn_only_conntrack(blob) is True


def test_build_payload_biz_ok_t3_not_syn_when_time_wait_only() -> None:
    """核查通过 + TIME_WAIT conntrack → T3 为「是（本机探测）」而非「见 SYN」。"""
    d = DiagnosisResult(diagnosis_type="business_diagnose", root_causes=[])
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
                            "status": "ok",
                            "host": "172.253.118.136",
                            "data": {"port_open": True},
                        }
                    ],
                }
            ],
            "biz_target_ips": ["172.253.118.136"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 172.253.118.136": (
                    "ipv4 2 icmp 1 0 src=10.10.25.3 dst=172.253.118.136 [UNREPLIED]\n"
                    "ipv4 2 tcp 6 0 TIME_WAIT src=10.10.25.3 dst=172.253.118.136 dport=443"
                ),
            },
        },
    }
    payload = build_commercial_delivery_payload(
        trace_id="t-yt-verify",
        diagnosis=d,
        topology_dict={"pc_snapshot_included": True},
        targeted_probe=tp,
    )
    assert payload is not None
    t3 = next(row for row in payload.checklist if row["id"] == "T3")
    assert t3["status"] == "是（本机探测）"


def test_build_payload_business_probes_all_ok_headline() -> None:
    d = DiagnosisResult(diagnosis_type="deep_dive", root_causes=[])
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [
                {
                    "domain": "svc.example",
                    "port": 443,
                    "dns": {"status": "ok", "data": {"resolved_ips": ["203.0.113.1"]}},
                    "tcp": [
                        {
                            "status": "ok",
                            "host": "203.0.113.1",
                            "data": {"port_open": True},
                        }
                    ],
                }
            ],
            "biz_target_ips": ["203.0.113.1"],
            "raw_outputs": {},
        },
    }
    payload = build_commercial_delivery_payload(
        trace_id="t-ok",
        diagnosis=d,
        topology_dict={"pc_snapshot_included": True},
        targeted_probe=tp,
    )
    assert payload is not None
    assert "本机业务探测" in payload.headline
    assert "已成功" in payload.headline
