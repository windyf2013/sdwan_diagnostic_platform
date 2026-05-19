"""纯深度诊断报告呈现层（report_deep_dive_outcome）。"""

from __future__ import annotations

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity
from sdwan_desktop.services.reporter.deep_dive_report_presentation import (
    build_deep_dive_report_outcome,
)


def test_cpe_focused_outcome_no_issues() -> None:
    d = DiagnosisResult(diagnosis_type="deep_dive", root_causes=[], summary="ok")
    topo: dict = {}
    out = build_deep_dive_report_outcome(
        diagnosis=d,
        topology_dict=topo,
        targeted_probe=None,
    )
    assert out["mode"] == "cpe_focus"
    assert out["verdict"] == "正常"
    assert "CPE 可达" in out["phenomenon"]
    assert not out["primary_fault"]


def test_cpe_focused_outcome_cpe_unreachable() -> None:
    causes = [
        RootCause(
            cause_id="CPE-001",
            title="CPE 不可达",
            description="ssh fail",
            severity=Severity.CRITICAL,
            confidence=0.95,
        )
    ]
    d = DiagnosisResult(diagnosis_type="deep_dive", root_causes=causes)
    out = build_deep_dive_report_outcome(
        diagnosis=d,
        topology_dict={},
        targeted_probe=None,
    )
    assert out["primary_fault"] == "CPE 不可达"
    assert "不可达" in out["phenomenon"]


def test_with_business_probe_delegates_to_joint_outcome() -> None:
    causes = [
        RootCause(
            cause_id="BIZ-TCP-001",
            title="tcp",
            description="d",
            severity=Severity.ERROR,
            confidence=0.8,
        )
    ]
    d = DiagnosisResult(diagnosis_type="deep_dive", root_causes=causes)
    tp = {
        "status": "partial",
        "data": {
            "business_probes": [
                {
                    "domain": "svc.example",
                    "port": 443,
                    "dns": {"status": "ok", "data": {"resolved_ips": ["203.0.113.1"]}},
                    "tcp": [
                        {
                            "host": "203.0.113.1",
                            "port": 443,
                            "status": "fail",
                            "error": "timeout",
                        }
                    ],
                    "trace": [],
                }
            ],
            "raw_outputs": {},
        },
    }
    topo: dict = {}
    out = build_deep_dive_report_outcome(
        diagnosis=d,
        topology_dict=topo,
        targeted_probe=tp,
    )
    assert out["mode"] == "with_business_probe"
    assert out["has_business_probes"] is True
    assert out.get("overall") == "fail"
    assert out.get("phenomenon")
