"""Raisecom 动态 show interface 推断单元测试。"""

from sdwan_desktop.services.collector.raisecom_interface_discovery import (
    build_raisecom_extra_show_interface_commands,
    discover_raisecom_extra_interface_names,
)


def test_discover_vxlan_from_policy_route_and_link_detect() -> None:
    raw = {
        "show running-config": "tunnel tunnel49 \n type vxlan\n peer 11.24.0.1\nexit\n",
        "show ip route": "",
        "show link detect": "master vxlan2500176 dest 5.96.1.198 backup vxlan2500176 3 3 scene_2 up none",
        "diagnose:ip route show table 100": "default via 5.96.1.198 dev vxlan2500176 metric 10 \n",
        "diagnose:ip route show table 99": "",
    }
    names = discover_raisecom_extra_interface_names(raw)
    assert "vxlan2500176" in names


def test_build_commands_skips_when_already_present() -> None:
    raw = {
        "show running-config": "",
        "show ip route": "default via 1.1.1.1 dev vxlan1111 weight: 1",
        "show link detect": "",
        "diagnose:ip route show table 99": "",
        "diagnose:ip route show table 100": "",
        "show interface vxlan1111": "Interface vxlan1111 is up\n",
    }
    cmds = build_raisecom_extra_show_interface_commands(raw)
    assert cmds == []
