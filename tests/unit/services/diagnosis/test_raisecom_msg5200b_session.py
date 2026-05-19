"""Tests for Raisecom 5200B joint overlay datapath gate."""

from __future__ import annotations

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, SdwanPolicy, VpnTunnelInfo
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    compute_joint_overlay_datapath_gate,
    joint_overlay_should_run_policy_flow,
)


def _tp_with_conntrack(dst_biz_ip: str, conntrack_line: str) -> dict:
    return {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "svc.example", "port": 443, "dns": {"status": "ok"}}],
            "biz_target_ips": [dst_biz_ip],
            "raw_outputs": {f"diagnose:nf_conntrack grep {dst_biz_ip}": conntrack_line},
        },
    }


def _topo_pc(pc_ip: str) -> dict:
    return {
        "pc_node_id": "pc-1",
        "nodes": [{"id": "pc-1", "type": "pc", "ip_address": pc_ip}],
    }


def _raisecom_cpe() -> CpeConfiguration:
    return CpeConfiguration(vendor="raisecom", model="MSG5200B", version="1.0", hostname="cpe1")


def test_raisecom_no_conntrack_suppresses_overlay() -> None:
    cpe = _raisecom_cpe()
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "x.example", "port": 443}],
            "biz_target_ips": ["203.0.113.10"],
            "raw_outputs": {"diagnose:nf_conntrack grep 203.0.113.10": ""},
        },
    }
    g = compute_joint_overlay_datapath_gate(tp, cpe, _topo_pc("192.168.54.10"))
    assert g.show_overlay_tunnel_strip is False
    assert g.overlay_evidence_positive is False
    assert g.rule_case == "raisecom_no_conntrack_sampling"
    assert joint_overlay_should_run_policy_flow(tp, cpe, _topo_pc("192.168.54.10")) is False


def test_raisecom_policy_prefix_match_shows_overlay() -> None:
    cpe = _raisecom_cpe()
    cpe.sdwan_policies = [SdwanPolicy(name="p1", source="192.168.54.0/24")]
    # grep 键为声明业务 IP；会话 DIP 为隧道下一跳（非 D0 全公网 Underlay）
    tp = _tp_with_conntrack(
        "203.0.113.10",
        "tcp ESTABLISHED src=192.168.54.10 dst=5.96.1.26 sport=1111 dport=443",
    )
    g = compute_joint_overlay_datapath_gate(tp, cpe, _topo_pc("192.168.54.10"))
    assert g.show_overlay_tunnel_strip is True
    assert g.overlay_evidence_positive is True
    assert g.rule_case == "raisecom_session_matched_policy_prefix"
    assert g.evidence_tier == "precise"


def test_raisecom_prefix_mismatch_all_dip_tunnel_heuristic() -> None:
    cpe = _raisecom_cpe()
    cpe.sdwan_policies = [SdwanPolicy(name="p1", source="192.168.54.0/24")]
    cpe.vpn_tunnels = [VpnTunnelInfo(remote_ip="198.51.100.2")]
    # 会话文本中仅出现隧道侧 dst=（grep 键仍为声明业务目的 IP，与现网「采样块」契约一致）
    tp = _tp_with_conntrack(
        "203.0.113.10",
        "tcp ESTABLISHED src=10.0.0.5 dst=5.96.1.26 sport=2222 dport=443 packets=1 bytes=40",
    )
    g = compute_joint_overlay_datapath_gate(tp, cpe, _topo_pc("10.0.0.5"))
    assert g.rule_case == "raisecom_all_dip_tunnel_precise"
    assert g.evidence_tier == "precise"
    assert g.show_overlay_tunnel_strip is True


def test_raisecom_prefix_mismatch_public_dip_suppresses() -> None:
    cpe = _raisecom_cpe()
    cpe.sdwan_policies = [SdwanPolicy(name="p1", source="192.168.54.0/24")]
    tp = _tp_with_conntrack(
        "203.0.113.10",
        "tcp ESTABLISHED src=10.0.0.5 dst=203.0.113.10 sport=2222 dport=443 "
        "packets=1 bytes=40 src=203.0.113.10 dst=8.8.8.8 sport=443 dport=2222",
    )
    g = compute_joint_overlay_datapath_gate(tp, cpe, _topo_pc("10.0.0.5"))
    assert g.rule_case == "raisecom_underlay_no_overlay_evidence"
    assert g.evidence_tier == "underlay_only"
    assert g.show_overlay_tunnel_strip is False


def test_raisecom_193136_bidirectional_vxlan_overlay() -> None:
    """现网回放：NAT 后 src + 业务 dst + 回程 vxlan 口（同行双向）。"""
    from sdwan_desktop.core.types.cpe_config import InterfaceInfo

    cpe = _raisecom_cpe()
    cpe.interfaces = [InterfaceInfo(name="vxlan5", ip_address="8.1.3.2")]
    line = (
        "tcp TIME_WAIT src=10.10.25.3 dst=172.253.118.91 sport=59974 dport=443 "
        "src=172.253.118.91 dst=8.1.3.2 sport=443 dport=59974"
    )
    tp = _tp_with_conntrack("172.253.118.91", line)
    g = compute_joint_overlay_datapath_gate(tp, cpe, _topo_pc("10.10.100.161"))
    assert g.rule_case == "raisecom_overlay_conntrack_bidirectional"
    assert g.evidence_tier == "precise"
    assert g.show_overlay_tunnel_strip is True


def test_raisecom_mixed_dip_not_d0() -> None:
    cpe = _raisecom_cpe()
    tp = _tp_with_conntrack(
        "203.0.113.10",
        "tcp ESTABLISHED src=10.0.0.5 dst=5.96.1.26 sport=1 dport=443 "
        "tcp ESTABLISHED src=10.0.0.5 dst=203.0.113.10 sport=2 dport=443",
    )
    g = compute_joint_overlay_datapath_gate(tp, cpe, _topo_pc("10.0.0.5"))
    assert g.rule_case != "raisecom_d0_public_underlay_veto"


def test_raisecom_public_dip_no_vxlan_underlay_not_d0() -> None:
    """废除 D0：仅公网 dip、无 vxlan 回程 → underlay，非 d0_public_underlay_veto。"""
    cpe = _raisecom_cpe()
    tp = _tp_with_conntrack(
        "203.0.113.10",
        "tcp ESTABLISHED src=10.0.0.5 dst=203.0.113.10 sport=1 dport=443",
    )
    g = compute_joint_overlay_datapath_gate(tp, cpe, _topo_pc("10.0.0.5"))
    assert g.rule_case != "raisecom_d0_public_underlay_veto"
    assert g.rule_case == "raisecom_underlay_no_overlay_evidence"


def test_non_raisecom_conntrack_alone_does_not_show_overlay() -> None:
    cpe = CpeConfiguration(vendor="cisco", model="vedge", version="20.1", hostname="v1")
    tp = _tp_with_conntrack(
        "203.0.113.10",
        "tcp SYN_SENT src=10.1.1.5 dst=203.0.113.10 sport=54321 dport=443",
    )
    g = compute_joint_overlay_datapath_gate(tp, cpe, None)
    assert g.rule_case == "non_raisecom_no_overlay_evidence"
    assert g.show_overlay_tunnel_strip is False
