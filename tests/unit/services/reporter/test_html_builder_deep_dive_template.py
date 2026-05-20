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
        {
            "report_html_h1": "业务路径联合诊断报告",
            "nodes": [],
            "edges": [],
            "report_joint_reading_layer": {
                "verdict_label": "探测通过",
                "verdict_tone": "success",
                "headline": "测试目标：本机正常",
                "takeaway_bullets": [
                    {"key": "本机", "text": "通过"},
                    {"key": "路径", "text": "Overlay"},
                    {"key": "下一步", "text": "留档"},
                ],
                "path_summary_short": "走 Overlay",
                "reading_steps": [{"title": "①", "text": "t", "anchor": "#x"}],
                "audience_hints": [{"role": "值班", "focus": "结论"}],
                "root_causes_heuristic_only": True,
                "root_causes_nav_label": "配置核对 (1)",
                "root_causes_section_title": "配置核对（启发式 · 非故障）",
                "root_causes_badge_text": "1 条待核对",
            },
        },
    )
    assert "report-joint-hero" in html
    assert 'id="report-joint-outcome"' in html
    assert "核查结论" in html
    assert "如何阅读本报告" in html
    assert 'id="report-joint-lead"' not in html
    assert "探测结论（技术层）" not in html
    assert "本报告结论" not in html
    assert "meta-item--more" not in html
    assert "report-joint-probe-dl--lead" in html or "report-joint-one-liner" in html


def test_build_deep_dive_joint_renders_path_evidence_blocks() -> None:
    """联合模板应渲染路径旁证 / 可达性 / 声明路径等证据块。"""
    builder = HtmlReportBuilder()
    r = DiagnosisResult(
        diagnosis_type="deep_dive",
        summary="s",
        severity=Severity.INFO,
        overall_confidence=0.5,
        root_causes=[],
    )
    topo = {
        "report_html_h1": "业务路径联合诊断报告",
        "nodes": [],
        "edges": [],
        "joint_path_evidence": {
            "rule_case": "raisecom_overlay_conntrack_bidirectional",
            "evidence_tier": "precise",
            "evidence_tier_label": "精确定位",
            "datapath_banner_short": "【精确定位】走 Overlay",
            "l1_session": {"summary": "L1 ok", "sample_lines": ["line1"]},
            "l3_fib": {"summary": "L3 ok", "excerpts": ["route1"]},
            "l5_trace": {"narrative_hint": "早期公网", "egress_shape": "early_public"},
            "reachability": {
                "s1_status": "ok",
                "s1_summary": "S1 ok",
                "s2_status": "miss",
                "s2_summary": "S2 nh down",
            },
        },
        "declared_business_path_analysis": {
            "config_intent": "sdwan_overlay",
            "observed_plane": "overlay",
            "confidence": "precise",
            "url_group_analysis": {
                "summary": "hit abroad",
                "link_protect_summary": "lp ok",
                "effective_group": "abroad",
                "effective_selection_reason": "suffix match",
                "policy_intent_one_liner": "SD-WAN",
                "matched_groups": [{"name": "abroad", "priority": 150, "security_ip_enabled": False}],
                "per_group_security": [{"group": "abroad", "security_ip_enabled": False, "pc_in_list": None}],
            },
            "reconcile": {"summary_for_delivery": "match", "break_point": None},
            "policy_chain_contrast": {
                "steps": [
                    {
                        "stage_id": "mangle",
                        "config_status": "match",
                        "runtime_status": "match",
                        "narrative": "MARK ok",
                        "config_excerpt": "mark 99",
                        "runtime_excerpt": "pkts=1",
                    }
                ]
            },
            "reachability": {"s1_summary": "S1", "s2_summary": "S2"},
        },
    }
    html = builder.build_deep_dive_report(r, topo)
    assert "路径旁证（精确定位" in html
    assert "L5 Traceroute" in html
    assert "可达性（S1 / S2）" in html
    assert "link-protect" in html
    assert "mangle 配置/运行节选" in html


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
    assert 'id="report-joint-outcome"' not in html
    assert "meta-item--more" not in html
    assert 'id="summary"' in html
    assert "report-deep-dive-outcome" in html
    assert "专检结论" in html
