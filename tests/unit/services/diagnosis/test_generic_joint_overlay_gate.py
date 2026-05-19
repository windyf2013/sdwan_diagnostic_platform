"""Tests for non-5200B joint overlay gate."""

from __future__ import annotations

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.diagnosis.generic_joint_overlay_gate import (
    compute_generic_joint_overlay_gate,
)


def _tp_conntrack_only() -> dict:
    return {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "x.example", "port": 443}],
            "biz_target_ips": ["203.0.113.10"],
            "raw_outputs": {
                "diagnose:nf_conntrack grep 203.0.113.10": (
                    "tcp SYN_SENT src=10.1.1.5 dst=203.0.113.10 sport=1 dport=443"
                )
            },
        },
    }


def test_generic_conntrack_without_trace_no_overlay() -> None:
    cpe = CpeConfiguration(vendor="cisco", model="vedge", version="20", hostname="v1")
    g = compute_generic_joint_overlay_gate(_tp_conntrack_only(), cpe, None)
    assert g.rule_case == "non_raisecom_no_overlay_evidence"
    assert g.show_overlay_tunnel_strip is False
    assert g.evidence_tier == "underlay_only"
