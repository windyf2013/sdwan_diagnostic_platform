"""raisecom_msg5200b_session_path 单元测试。"""

from __future__ import annotations

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, InterfaceInfo
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session_path import (
    evaluate_session_path_evidence,
    parse_conntrack_line_bidirectional,
)


def test_parse_bidirectional_line() -> None:
    line = (
        "tcp TIME_WAIT src=10.10.25.3 dst=172.253.118.91 sport=1 dport=443 "
        "src=172.253.118.91 dst=8.1.3.2 sport=443 dport=1"
    )
    tup = parse_conntrack_line_bidirectional(line)
    assert tup is not None
    assert tup.forward_src == "10.10.25.3"
    assert tup.forward_dst == "172.253.118.91"
    assert tup.reply_dst == "8.1.3.2"


def test_evaluate_session_path_193136() -> None:
    cpe = CpeConfiguration(
        vendor="raisecom",
        model="MSG5200B",
        version="1",
        hostname="cpe",
        interfaces=[InterfaceInfo(name="vxlan5", ip_address="8.1.3.2")],
    )
    data = {
        "biz_target_ips": ["172.253.118.91"],
        "raw_outputs": {
            "diagnose:nf_conntrack grep 172.253.118.91": (
                "tcp TIME_WAIT src=10.10.25.3 dst=172.253.118.91 sport=1 dport=443 "
                "src=172.253.118.91 dst=8.1.3.2 sport=443 dport=1"
            ),
        },
    }
    ev = evaluate_session_path_evidence(data, cpe, "10.10.100.161")
    assert ev.overlay_path_confirmed is True
    assert ev.line_confirmed_count == 1


def test_two_forward_pairs_on_one_line_not_overlay() -> None:
    """同一行内两条单向会话（第二对 src≠正向 dst）不得误判为双向 overlay。"""
    cpe = CpeConfiguration(vendor="raisecom", model="MSG5200B", version="1", hostname="cpe")
    data = {
        "biz_target_ips": ["142.250.185.78"],
        "raw_outputs": {
            "diagnose:nf_conntrack grep 142.250.185.78": (
                "tcp ESTABLISHED src=10.0.0.5 dst=142.250.185.78 sport=1 dport=443 "
                "tcp ESTABLISHED src=10.0.0.5 dst=5.96.1.26 sport=2 dport=443"
            ),
        },
    }
    ev = evaluate_session_path_evidence(data, cpe, "10.0.0.5")
    assert ev.line_confirmed_count == 0
