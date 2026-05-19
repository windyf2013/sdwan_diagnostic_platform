"""拓扑后探测命令规划单元测试。"""

from sdwan_desktop.services.probe.planner import (
    extract_tunnel_peer_ips_from_cpe_configuration,
    plan_post_topology_probe_commands,
)
from unittest.mock import MagicMock


def test_plan_raisecom_includes_link_protect_and_url_group() -> None:
    cmds = plan_post_topology_probe_commands("raisecom_msg5200b")
    names = [c["name"] for c in cmds]
    assert "show link-protect status" in names
    assert "show url-group all domain all" in names
    assert "diagnose:ipset --list" in names


def test_plan_raisecom_includes_nf_conntrack_for_biz_ips() -> None:
    cmds = plan_post_topology_probe_commands(
        "raisecom_msg5200b",
        biz_target_ips=["69.171.235.22", "69.171.235.22", "8.8.8.8"],
    )
    names = [c["name"] for c in cmds]
    assert 'diagnose:cat /proc/rcios/net/netfilter/nf_conntrack | grep "69.171.235.22"' in names
    assert 'diagnose:cat /proc/rcios/net/netfilter/nf_conntrack | grep "8.8.8.8"' in names
    assert names.count('diagnose:cat /proc/rcios/net/netfilter/nf_conntrack | grep "69.171.235.22"') == 1


def test_plan_raisecom_skips_tunnel_peer_when_flag_false() -> None:
    cmds = plan_post_topology_probe_commands(
        "raisecom_msg5200b",
        biz_target_ips=["8.8.8.8"],
        tunnel_peer_ips=["10.0.0.1"],
        include_tunnel_peer_probes=False,
    )
    names = [c["name"] for c in cmds]
    assert any("nf_conntrack" in n for n in names)
    assert not any("ping -c 2" in n for n in names)


def test_plan_generic_empty() -> None:
    assert plan_post_topology_probe_commands("generic") == []


def test_plan_raisecom_tunnel_peer_ping_only() -> None:
    cmds = plan_post_topology_probe_commands(
        "raisecom_msg5200b",
        tunnel_peer_ips=["11.24.0.1", "11.25.0.1"],
    )
    names = [c["name"] for c in cmds]
    assert "diagnose:ping -c 2 11.24.0.1" in names
    assert "diagnose:ping -c 2 11.25.0.1" in names


def test_extract_tunnel_peer_ips_from_configuration() -> None:
    t1 = MagicMock(remote_ip="  5.0.1.1 ")
    t2 = MagicMock(remote_ip="5.0.1.1")
    cfg = MagicMock(vpn_tunnels=[t1, t2])
    assert extract_tunnel_peer_ips_from_cpe_configuration(cfg) == ["5.0.1.1"]
