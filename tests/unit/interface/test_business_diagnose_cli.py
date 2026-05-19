"""CLI business-diagnose smoke tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from sdwan_desktop.services.diagnosis.business_diagnosis import BusinessDiagnosisOutcome


@pytest.fixture
def runner():
    return CliRunner()


def _minimal_overlay_envelope(trace_id: str) -> dict:
    return {
        "status": "ok",
        "data": {
            "trace_id": trace_id,
            "status": "partial",
            "scenario_tags": [],
            "scenario_label": "（测试占位）",
            "checklist": [],
            "forwarding_note": "",
            "probe_evidence_notes": [],
            "error": None,
        },
        "error": None,
    }


async def _fake_execute_success_ok(flow_def, ctx, handlers):
    """模拟流程结束态：探测成功、无联合。"""
    outcome = BusinessDiagnosisOutcome(
        status="ok",
        business_probes=[
            {
                "domain": "a.example",
                "port": 443,
                "dns": {"status": "ok", "data": {}, "error": None},
                "tcp": [],
            }
        ],
        aggregate_error=None,
    )
    ctx.set("business_outcome", outcome)
    ctx.set("collect_pc", False)
    ctx.set("pc_snapshot", None)
    ctx.set("joint_needed", False)
    ctx.set("cpe_ready", False)
    ctx.set("allow_probe_only", False)
    ctx.set("run_joint", False)
    ctx.set("joint_done", False)
    ctx.set("causes_local", [])
    ctx.set("causes", [])
    ctx.set("overlay_policy_flow", _minimal_overlay_envelope(ctx.trace_id))
    return {}


async def _fake_execute_success_html(flow_def, ctx, handlers):
    outcome = BusinessDiagnosisOutcome(
        status="ok",
        business_probes=[],
        aggregate_error=None,
    )
    ctx.set("business_outcome", outcome)
    ctx.set("collect_pc", False)
    ctx.set("pc_snapshot", None)
    ctx.set("joint_needed", False)
    ctx.set("cpe_ready", False)
    ctx.set("allow_probe_only", False)
    ctx.set("run_joint", False)
    ctx.set("joint_done", False)
    ctx.set("causes_local", [])
    ctx.set("causes", [])
    ctx.set("overlay_policy_flow", _minimal_overlay_envelope(ctx.trace_id))
    return {}


async def _fake_execute_missing_cpe_exit2(flow_def, ctx, handlers):
    raise SystemExit(2)


async def _fake_execute_partial_allow(flow_def, ctx, handlers):
    outcome = BusinessDiagnosisOutcome(
        status="partial",
        business_probes=[
            {
                "domain": "x.example",
                "port": 443,
                "dns": {"status": "error", "data": None, "error": "SERVFAIL"},
                "tcp": [],
            }
        ],
        aggregate_error="dns",
    )
    ctx.set("business_outcome", outcome)
    ctx.set("collect_pc", False)
    ctx.set("pc_snapshot", None)
    ctx.set("joint_needed", True)
    ctx.set("cpe_ready", False)
    ctx.set("allow_probe_only", True)
    ctx.set("run_joint", False)
    ctx.set("joint_done", False)
    ctx.set("causes_local", [])
    ctx.set("causes", [])
    ctx.set("overlay_policy_flow", _minimal_overlay_envelope(ctx.trace_id))
    return {}


def test_business_diagnose_json_writes_file(runner, tmp_path):
    from sdwan_desktop.interface.cli.commands.business_diagnose import business_diagnose

    out_json = tmp_path / "biz.json"
    with patch(
        "sdwan_desktop.interface.cli.commands.business_diagnose.FlowRuntime.execute_flow",
        new=AsyncMock(side_effect=_fake_execute_success_ok),
    ):
        r = runner.invoke(
            business_diagnose,
            ["-b", "a.example", "--format", "json", "-o", str(out_json)],
        )
    assert r.exit_code == 0, r.output
    assert out_json.is_file()
    text = out_json.read_text(encoding="utf-8")
    assert "a.example" in text or "report_pack" in text
    assert '"report_pack"' in text
    assert "business_diagnose" in text


def test_business_diagnose_html_invokes_builder(runner, tmp_path):
    from sdwan_desktop.interface.cli.commands.business_diagnose import business_diagnose

    with patch(
        "sdwan_desktop.interface.cli.commands.business_diagnose.FlowRuntime.execute_flow",
        new=AsyncMock(side_effect=_fake_execute_success_html),
    ), patch(
        "sdwan_desktop.interface.cli.commands.business_diagnose.HtmlReportBuilder"
    ) as MockBuilder:
        inst = MagicMock()
        inst.build_business_diagnosis_report = MagicMock(return_value="<html/>")
        MockBuilder.return_value = inst
        r = runner.invoke(
            business_diagnose,
            ["-b", "x.example", "-o", str(tmp_path / "o.html")],
        )
    assert r.exit_code == 0, r.output
    inst.build_business_diagnosis_report.assert_called_once()


def test_business_diagnose_probe_failure_exits_2_without_cpe_or_allow(runner):
    from sdwan_desktop.interface.cli.commands.business_diagnose import business_diagnose

    with patch(
        "sdwan_desktop.interface.cli.commands.business_diagnose.FlowRuntime.execute_flow",
        new=AsyncMock(side_effect=_fake_execute_missing_cpe_exit2),
    ):
        r = runner.invoke(business_diagnose, ["-b", "x.example"])
    assert r.exit_code == 2, r.output


def test_business_diagnose_probe_failure_allow_probe_only_json_ok(runner, tmp_path):
    from sdwan_desktop.interface.cli.commands.business_diagnose import business_diagnose

    out_json = tmp_path / "biz_partial.json"
    with patch(
        "sdwan_desktop.interface.cli.commands.business_diagnose.FlowRuntime.execute_flow",
        new=AsyncMock(side_effect=_fake_execute_partial_allow),
    ):
        r = runner.invoke(
            business_diagnose,
            ["-b", "x.example", "--allow-probe-only", "--format", "json", "-o", str(out_json)],
        )
    assert r.exit_code == 0, r.output
    assert out_json.is_file()
    assert '"joint_diagnosis": false' in out_json.read_text(encoding="utf-8")
