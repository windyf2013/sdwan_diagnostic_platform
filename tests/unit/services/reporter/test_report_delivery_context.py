"""report_delivery_context：商用 report_pack 工厂与 html_builder 注入冒烟。"""

from __future__ import annotations

from pathlib import Path

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder
from sdwan_desktop.services.reporter.report_delivery_context import (
    ReportProductLine,
    biz_targets_from_business_probes,
    build_business_diagnose_pack,
    build_deep_dive_pack,
    build_quick_check_pack,
)


def test_build_quick_check_pack_fields() -> None:
    d = DiagnosisResult(diagnosis_type="quick_check", trace_id="t1", root_causes=[])
    pack = build_quick_check_pack(result=d)
    js = pack.as_template_dict()
    assert js["product_line"] == ReportProductLine.QUICK_CHECK.value
    assert js["trace_id"] == "t1"
    assert len(js["evidence_tiers"]) == 3


def test_build_business_joint_and_targets() -> None:
    d = DiagnosisResult(diagnosis_type="business_diagnosis_joint", trace_id="t2", root_causes=[])
    rows = [{"domain": "a.example", "port": 443}]
    pack = build_business_diagnose_pack(
        result=d,
        joint_mode=True,
        biz_targets=biz_targets_from_business_probes(rows),
        joint_failure_driven=True,
    )
    js = pack.as_template_dict()
    assert js["joint_mode"] is True
    assert "a.example:443" in js["product_subtitle"]
    assert "Post-failure" in js["product_title"] or "深挖" in js["product_title"]


def test_build_deep_dive_has_business_probe() -> None:
    d = DiagnosisResult(diagnosis_type="deep_dive", trace_id="t3", root_causes=[])
    pack = build_deep_dive_pack(result=d, has_business_probe=True)
    assert "叠加" in pack.product_subtitle


def test_html_builder_quick_check_renders_report_pack(tmp_path: Path) -> None:
    d = DiagnosisResult(
        diagnosis_type="quick_check",
        trace_id="t-x",
        summary="ok",
        root_causes=[],
        severity=Severity.INFO,
        overall_confidence=0.9,
    )
    out = tmp_path / "q.html"
    html = HtmlReportBuilder().build_quick_check_report(d, out)
    assert "报告定位与范围" in html
    assert out.is_file()
