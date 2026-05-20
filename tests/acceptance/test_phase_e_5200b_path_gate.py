"""Phase E 验收契约（P0）：禁止子集单测冒充完整验收。

由 ``scripts/verify_5200b_path_phase_e.py`` 聚合执行；本模块覆盖：
- enrichment 模块可导入且可写 topo
- joint_done 后 CLI 收尾路径（agentctl 曾触发的 NameError 回归）
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.diagnosis.business_diagnosis import BusinessDiagnosisOutcome
from sdwan_desktop.services.diagnosis.joint_business_topology_enrichment import (
    apply_joint_datapath_and_path_analysis,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    is_raisecom_msg5200b_cpe,
)
from tests.simulation.joint_report_matrix import (
    _raisecom_cpe,
    _standard_topology,
    _tp_base,
)


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


async def _fake_execute_joint_done(flow_def, ctx, handlers) -> dict:
    """联合 CPE 完成后的 CLI 上下文（触发 1136+ 行收尾逻辑）。"""
    topology = _standard_topology(pc_ip="192.168.54.17")
    cpe = _raisecom_cpe(
        policies=[],
    )
    cpe.vendor = "raisecom"
    cpe.model = "MSG5200B"
    tp = _tp_base(
        domain="biz.example",
        biz_ip="203.0.113.10",
        conntrack_line=(
            "tcp ESTABLISHED src=10.10.25.3 dst=203.0.113.10 sport=1 dport=443"
        ),
    )
    cpe_result = CollectorResult(success=True, data={"cpe_configuration": cpe})
    outcome = BusinessDiagnosisOutcome(
        status="ok",
        business_probes=[
            {
                "domain": "biz.example",
                "port": 443,
                "dns": {"status": "ok", "data": {"resolved_ips": ["203.0.113.10"]}},
                "tcp": [
                    {
                        "host": "203.0.113.10",
                        "port": 443,
                        "status": "ok",
                        "data": {"port_open": True},
                    }
                ],
            }
        ],
        aggregate_error=None,
    )
    ctx.set("business_outcome", outcome)
    ctx.set("collect_pc", False)
    ctx.set("pc_snapshot", None)
    ctx.set("joint_needed", False)
    ctx.set("joint_done", True)
    ctx.set("topology", topology)
    ctx.set("cpe_result", cpe_result)
    ctx.set("targeted_probe", tp)
    ctx.set("causes", [])
    ctx.set("overlay_policy_flow", _minimal_overlay_envelope(ctx.trace_id))
    return {}


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_apply_joint_datapath_enrichment_on_5200b() -> None:
    cpe = _raisecom_cpe()
    assert is_raisecom_msg5200b_cpe(cpe)
    topo: dict = {"pc_node_id": "pc-1", "nodes": []}
    tp = _tp_base(domain="youtube.com", biz_ip="142.250.185.78", conntrack_line="")
    gate = apply_joint_datapath_and_path_analysis(topo, tp, cpe)
    assert gate.rule_case
    assert "declared_business_datapath_banner" in topo


def test_business_diagnose_joint_done_json_post_flow(runner: CliRunner, tmp_path) -> None:
    """回归：联合完成后 JSON 输出须走过 _joint_overlay_gate_from_cli_context。"""
    from sdwan_desktop.interface.cli.commands.business_diagnose import business_diagnose

    out_json = tmp_path / "joint_done.json"
    with patch(
        "sdwan_desktop.interface.cli.commands.business_diagnose.FlowRuntime.execute_flow",
        new=AsyncMock(side_effect=_fake_execute_joint_done),
    ):
        result = runner.invoke(
            business_diagnose,
            ["-b", "biz.example", "--format", "json", "-o", str(out_json)],
        )
    assert result.exit_code == 0, result.output
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload.get("joint_diagnosis") is True
    assert payload.get("joint_overlay_rule_case")


def test_business_diagnose_joint_done_html_post_flow(runner: CliRunner, tmp_path) -> None:
    """回归：联合完成后 HTML 须走过 apply_joint_datapath_and_path_analysis。"""
    from sdwan_desktop.interface.cli.commands.business_diagnose import business_diagnose

    out_html = tmp_path / "joint_done.html"
    with patch(
        "sdwan_desktop.interface.cli.commands.business_diagnose.FlowRuntime.execute_flow",
        new=AsyncMock(side_effect=_fake_execute_joint_done),
    ):
        result = runner.invoke(
            business_diagnose,
            ["-b", "biz.example", "-o", str(out_html)],
        )
    assert result.exit_code == 0, result.output
    text = out_html.read_text(encoding="utf-8")
    assert len(text) > 1000
    assert "url-group 与声明业务路径分析" in text or "路径" in text
