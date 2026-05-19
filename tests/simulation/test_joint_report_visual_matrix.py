"""仿真矩阵：生成 HTML 并校验门控/呈现关键字。"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.simulation.joint_report_matrix import (
    _DEFAULT_OUT,
    all_scenarios,
    generate_scenario_html,
    run_matrix,
)


@pytest.fixture(scope="module")
def matrix_output_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("sim_matrix")
    return d


@pytest.mark.parametrize(
    "scenario",
    all_scenarios(),
    ids=[s.scenario_id for s in all_scenarios()],
)
def test_scenario_gate_and_html(scenario, matrix_output_dir: Path) -> None:
    result = generate_scenario_html(scenario, matrix_output_dir)
    assert result.checks.get("html_exists"), f"HTML missing for {scenario.scenario_id}"
    assert result.checks.get("rule_case"), (
        f"rule_case expected {scenario.expected_rule_case} got {result.rule_case}"
    )
    assert result.checks.get("show_overlay"), (
        f"show_overlay expected {scenario.expected_show_overlay} got {result.show_overlay}"
    )
    if scenario.expected_evidence_tier:
        assert result.checks.get("evidence_tier"), (
            f"tier expected {scenario.expected_evidence_tier} got {result.evidence_tier}"
        )


def test_matrix_index_and_all_pass(matrix_output_dir: Path) -> None:
    index, results = run_matrix(matrix_output_dir)
    assert index.is_file()
    assert len(results) == len(all_scenarios())
    failed = [r for r in results if not all(r.checks.values())]
    assert not failed, f"Failed scenarios: {[r.scenario_id for r in failed]}"


@pytest.mark.integration
def test_generate_reports_to_repo_reports_dir() -> None:
    """写入 reports/sim_matrix 供人工目视（本地验收）。"""
    index, results = run_matrix(_DEFAULT_OUT)
    assert index == _DEFAULT_OUT / "index.html"
    assert all(r.html_path.exists() for r in results)
