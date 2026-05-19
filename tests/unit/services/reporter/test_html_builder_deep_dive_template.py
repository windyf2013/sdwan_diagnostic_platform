"""HtmlReportBuilder：深度诊断模板选用（联合 vs 纯深度）。"""

from __future__ import annotations

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder


def test_build_deep_dive_uses_joint_template_when_report_html_h1() -> None:
    """topology 含 report_html_h1 时应渲染 deep_dive_joint_ux（含联合 hero 专有结构）。"""
    builder = HtmlReportBuilder()
    r = DiagnosisResult(
        diagnosis_type="deep_dive",
        summary="s",
        severity=Severity.INFO,
        overall_confidence=0.5,
        root_causes=[],
    )
    html = builder.build_deep_dive_report(
        r,
        {"report_html_h1": "业务路径联合诊断报告", "nodes": [], "edges": []},
    )
    assert "report-joint-hero" in html
    assert "report-joint-secondary-details" in html


def test_build_deep_dive_uses_legacy_template_without_report_html_h1() -> None:
    """纯深度诊断无 report_html_h1 时仍用 deep_dive.html（业务路径式扁平结构）。"""
    builder = HtmlReportBuilder()
    r = DiagnosisResult(
        diagnosis_type="deep_dive",
        summary="s",
        severity=Severity.INFO,
        overall_confidence=0.5,
        root_causes=[],
    )
    topo = {
        "nodes": [],
        "edges": [],
        "report_deep_dive_outcome": {
            "mode": "cpe_focus",
            "verdict": "正常",
            "phenomenon": "CPE 可达",
            "primary_fault": "",
            "primary_narrative": "n",
            "ruled_out": [],
            "secondary_findings": [],
            "has_business_probes": False,
        },
    }
    html = builder.build_deep_dive_report(r, topo)
    assert "report-joint-secondary-details" not in html
    assert 'id="report-joint-outcome"' not in html
    assert 'id="summary"' in html
    assert "report-deep-dive-outcome" in html
    assert "专检结论" in html
