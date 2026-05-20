"""joint_report_reading_layer：首屏人类可读结论与阅读指引。"""

from __future__ import annotations

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity
from sdwan_desktop.services.reporter.joint_report_reading_layer import (
    build_joint_report_reading_layer,
)


def _cause(cause_id: str, sev: Severity = Severity.WARNING) -> RootCause:
    return RootCause(
        cause_id=cause_id,
        title=cause_id,
        severity=sev,
        confidence=0.64,
        description="",
        evidence_refs=[],
    )


def test_probe_ok_heuristic_root_causes_marked_review_not_failure() -> None:
    po = {
        "overall": "ok",
        "targets_line": "www.youtube.com:443",
        "phenomenon": "www.youtube.com:443：本机 DNS/TCP 探测通过",
        "primary_fault": "",
        "secondary_findings": [{"id": "CPE-003", "label": "x", "note": "y"}],
    }
    topo = {
        "report_html_business_targets_line": "www.youtube.com:443",
        "topology_joint_presentation": {
            "business_probe_all_ok": True,
            "show_business_flow_overlay": True,
            "evidence_tier": "precise",
            "egress_shape": "early_public",
        },
        "declared_business_datapath_banner": "【精确定位】走 Overlay",
    }
    lead = build_joint_report_reading_layer(
        probe_outcome=po,
        topology_dict=topo,
        diagnosis=DiagnosisResult(
            diagnosis_type="x",
            summary="s",
            severity=Severity.INFO,
            overall_confidence=0.88,
            root_causes=[_cause("CPE-003"), _cause("CPE-004")],
        ),
        joint_failure_driven=False,
    )
    assert lead["verdict_label"] == "探测通过"
    assert lead["verdict_tone"] == "success"
    assert lead["root_causes_heuristic_only"] is True
    assert "配置核对" in lead["root_causes_nav_label"]
    assert "静态比对" in lead["headline"] or "配置核对" in lead["headline"]
    assert len(lead["takeaway_bullets"]) == 2
    assert not any(b["key"] == "下一步" for b in lead["takeaway_bullets"])
    assert not any("值班" in h["role"] for h in lead["audience_hints"])
    assert "Overlay" in lead["path_summary_short"]


def test_probe_fail_shows_error_tone() -> None:
    po = {"overall": "fail", "targets_line": "x:443", "phenomenon": "TCP fail"}
    lead = build_joint_report_reading_layer(
        probe_outcome=po,
        topology_dict={},
        diagnosis=DiagnosisResult(
            diagnosis_type="x",
            summary="s",
            severity=Severity.ERROR,
            overall_confidence=0.5,
            root_causes=[_cause("BIZ-TCP-001", Severity.ERROR)],
        ),
        joint_failure_driven=True,
    )
    assert lead["verdict_label"] == "探测未通过"
    assert lead["verdict_tone"] == "error"
    assert lead["root_causes_heuristic_only"] is False
