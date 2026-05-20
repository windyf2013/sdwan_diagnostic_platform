"""Phase E：path_matrix 场景契约（无 HTML，快速回归）。"""

from __future__ import annotations

from tests.simulation.joint_report_matrix import all_scenarios, _path_matrix_checks


def test_path_matrix_scenarios_contract() -> None:
    path_scenarios = [s for s in all_scenarios() if "path_matrix" in s.tags]
    assert len(path_scenarios) >= 4
    for sc in path_scenarios:
        tp = sc.build_targeted_probe()
        cpe = sc.build_cpe()
        topo = sc.build_topology()
        checks, intent, outcome, bp = _path_matrix_checks(sc, tp, cpe, topo)
        assert checks.get("path_analysis_ok"), sc.scenario_id
        failed = [k for k, v in checks.items() if not v]
        assert not failed, f"{sc.scenario_id} failed {failed} intent={intent} outcome={outcome} bp={bp}"
