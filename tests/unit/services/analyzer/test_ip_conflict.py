"""IP-002 ARP 冲突检测单元测试。"""

from sdwan_desktop.core.types.system import ArpEntry
from sdwan_desktop.services.analyzer.rules.system import (
    find_ip_conflicts_from_arp,
    _build_ip_002_message,
)


class _Ctx:
    def __init__(self, arp_table):
        self.arp_table = arp_table


def test_find_ip_conflicts_same_ip_different_mac():
    arp = [
        ArpEntry(ip_address="192.168.1.10", mac_address="aa:bb:cc:dd:ee:01", interface="eth0"),
        ArpEntry(ip_address="192.168.1.10", mac_address="aa:bb:cc:dd:ee:02", interface="wlan0"),
    ]
    conflicts = find_ip_conflicts_from_arp(arp)
    assert len(conflicts) == 1
    assert conflicts[0]["ip"] == "192.168.1.10"
    assert len(conflicts[0]["entries"]) == 2


def test_build_ip_002_message_lists_ip_and_mac():
    arp = [
        ArpEntry(ip_address="10.0.0.5", mac_address="11:22:33:44:55:66", interface=""),
        ArpEntry(ip_address="10.0.0.5", mac_address="aa:bb:cc:dd:ee:ff", interface="eth1"),
    ]
    msg = _build_ip_002_message(_Ctx(arp))
    assert "10.0.0.5" in msg
    assert "11:22:33:44:55:66" in msg
    assert "aa:bb:cc:dd:ee:ff" in msg
