"""Raisecom MSG5200A 解析器扩展能力测试。"""

from sdwan_desktop.services.parser.vendor.raisecom_msg5200 import RaisecomMsg5200Parser


def test_parse_nf_conntrack_lines() -> None:
    parser = RaisecomMsg5200Parser()
    raw = (
        "tcp      6 117 SYN_SENT src=10.10.100.161 dst=69.171.235.22 sport=50123 dport=443 packets=1 bytes=60 [UNREPLIED]\n"
        "tcp      6 431 ESTABLISHED src=10.10.100.161 dst=69.171.235.22 sport=50124 dport=443 packets=12 bytes=1234 [ASSURED]"
    )
    entries = parser.parse_nf_conntrack(raw)
    assert len(entries) == 2
    assert entries[0].proto == "tcp"
    assert entries[0].dst == "69.171.235.22"
    assert entries[0].dport == 443
    assert entries[0].state in ("SYN_SENT", "UNREPLIED")
    assert entries[1].state in ("ESTABLISHED", "ASSURED")


def test_parse_all_reads_nf_conntrack_saved_keys() -> None:
    parser = RaisecomMsg5200Parser()
    raw_outputs = {
        "show version": "RCIOS version : 4.23.1.20250805\nProduct Name: MSG5200-GEC-8E\nhost#",
        "show running-config": "hostname cpe-a\n",
        "diagnose:nf_conntrack grep 69.171.235.22": (
            "tcp 6 117 SYN_SENT src=10.10.100.161 dst=69.171.235.22 sport=50123 dport=443 packets=1 bytes=60 [UNREPLIED]"
        ),
    }
    parser.parse_all(raw_outputs)
    assert len(parser.nf_conntrack_entries) == 1
    assert parser.nf_conntrack_entries[0].dst == "69.171.235.22"
