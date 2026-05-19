"""declared_business_datapath：声明业务与 Overlay/隧道路径的实证口径。"""

from __future__ import annotations

from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    declared_business_flow_has_verified_overlay_tunnel_evidence,
    infer_declared_business_datapath_verdict,
    targeted_probe_has_business_target_conntrack_hits,
)


def test_infer_verdict_always_unverified_with_valid_envelope() -> None:
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "x.example", "port": 443}],
            "biz_target_ips": ["1.2.3.4"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 1.2.3.4": "l2tp ... dst=1.2.3.4",
            },
        },
    }
    assert infer_declared_business_datapath_verdict(tp) == "unverified"
    assert targeted_probe_has_business_target_conntrack_hits(tp) is True
    assert declared_business_flow_has_verified_overlay_tunnel_evidence(tp) is True


def test_infer_verdict_unverified_empty_envelope() -> None:
    assert infer_declared_business_datapath_verdict(None) == "unverified"
    assert targeted_probe_has_business_target_conntrack_hits(None) is False


def test_conntrack_hits_false_when_grep_empty() -> None:
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "x.example", "port": 443}],
            "biz_target_ips": ["1.2.3.4"],
            "raw_outputs": {"diagnose:nf_conntrack grep 1.2.3.4": ""},
        },
    }
    assert targeted_probe_has_business_target_conntrack_hits(tp) is False
