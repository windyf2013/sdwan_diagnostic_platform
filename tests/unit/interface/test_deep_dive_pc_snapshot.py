"""深度诊断：PC 快照 → 拓扑输入（主 IPv4 选取）。"""

from sdwan_desktop.services.topology.pc_topology_input import snapshot_to_topology_input


def test_primary_ip_prefers_same_slash24_as_default_gateway():
    snap = {
        "hostname": "pc-a",
        "os_version": "Windows 10",
        "adapters": [
            {
                "name": "NIC-A",
                "is_connected": True,
                "default_gateway": "10.10.100.254",
                "ip_addresses": ["172.16.72.161", "10.10.100.161"],
            },
        ],
        "routes": [],
        "ip_config": None,
    }
    out = snapshot_to_topology_input(snap)
    assert out["primary_ip"] == "10.10.100.161"
    assert out["default_gateway"] == "10.10.100.254"


def test_primary_ip_from_route_when_adapter_has_no_gateway():
    snap = {
        "hostname": "pc-b",
        "os_version": "Windows 10",
        "adapters": [
            {
                "name": "NIC-1",
                "is_connected": True,
                "default_gateway": None,
                "ip_addresses": ["172.16.1.10", "192.168.50.20"],
            },
        ],
        "routes": [
            {
                "destination": "0.0.0.0",
                "netmask": "0.0.0.0",
                "gateway": "192.168.50.1",
                "interface": "NIC-1",
                "metric": 0,
            }
        ],
        "ip_config": None,
    }
    out = snapshot_to_topology_input(snap)
    assert out["primary_ip"] == "192.168.50.20"
    assert out["default_gateway"] == "192.168.50.1"
