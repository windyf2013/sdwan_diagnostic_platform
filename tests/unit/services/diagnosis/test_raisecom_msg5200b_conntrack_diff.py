"""raisecom_msg5200b_conntrack_diff 单测。"""

from sdwan_desktop.services.diagnosis.raisecom_msg5200b_conntrack_diff import (
    evaluate_conntrack_diff_evidence,
)


def test_diff_finds_nat_session_sip_mismatch() -> None:
    data = {
        "biz_target_ips": ["142.250.185.78"],
        "business_probes": [{"domain": "x.com", "port": 443, "tcp": [], "dns": {}}],
        "raw_outputs": {
            "diagnose:nf_conntrack baseline grep 142.250.185.78": "",
            "diagnose:nf_conntrack grep 142.250.185.78": (
                "tcp 6 431999 src=192.168.10.5 dst=142.250.185.78 sport=54321 dport=443 "
                "src=142.250.185.78 dst=192.168.10.5 sport=443 dport=54321"
            ),
        },
    }
    ev = evaluate_conntrack_diff_evidence(data, None, pc_ip="192.168.1.100")
    assert ev.has_baseline is True
    assert ev.used_diff is True
    assert len(ev.matched_tuples) == 1
    assert ev.sip_mismatch_relaxed is True
    assert ev.matched_tuples[0].forward_dst == "142.250.185.78"


def test_diff_subtracts_baseline_line() -> None:
    line = "tcp 6 431999 src=10.0.0.1 dst=8.8.8.8 sport=1 dport=443"
    data = {
        "biz_target_ips": ["8.8.8.8"],
        "business_probes": [{"domain": "d", "port": 443}],
        "raw_outputs": {
            "diagnose:nf_conntrack baseline grep 8.8.8.8": line,
            "diagnose:nf_conntrack grep 8.8.8.8": line,
        },
    }
    ev = evaluate_conntrack_diff_evidence(data, None, pc_ip="10.0.0.1")
    assert ev.delta_lines == []
    assert ev.matched_tuples == []
