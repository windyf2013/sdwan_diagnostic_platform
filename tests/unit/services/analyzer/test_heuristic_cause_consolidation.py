"""启发式根因综合：单条结论、禁止堆叠。"""

from __future__ import annotations

from sdwan_desktop.core.types.diagnosis import RootCause, Severity
from sdwan_desktop.services.analyzer.heuristic_cause_consolidation import (
    CONSOLIDATED_CONFIG_HEURISTIC_ID,
    build_heuristic_consolidation_context,
    consolidate_heuristic_root_causes,
)


def _cause(cause_id: str, description: str = "x") -> RootCause:
    return RootCause(
        cause_id=cause_id,
        title=cause_id,
        description=description,
        severity=Severity.WARNING,
        confidence=0.8,
        evidence_refs=[],
    )


def test_consolidates_cpe003_and_cpe004_in_business_joint() -> None:
    causes = [_cause("CPE-003"), _cause("CPE-004"), _cause("BIZ-TCP-001")]
    tp = {
        "status": "ok",
        "data": {
            "business_probes": [{"domain": "x.com", "port": 443}],
            "biz_target_ips": ["1.2.3.4"],
        },
    }
    ctx = build_heuristic_consolidation_context(causes, targeted_probe=tp)
    out = consolidate_heuristic_root_causes(causes, ctx, targeted_probe=tp)
    assert ctx.policy_mismatch and ctx.nat_mismatch
    ids = {c.cause_id for c in out}
    assert "CPE-003" not in ids
    assert "CPE-004" not in ids
    assert CONSOLIDATED_CONFIG_HEURISTIC_ID in ids
    consolidated = next(c for c in out if c.cause_id == CONSOLIDATED_CONFIG_HEURISTIC_ID)
    assert "【与" not in consolidated.description
    assert consolidated.description.count("会话证据") <= 1


def test_skips_consolidation_without_business_probe_context() -> None:
    causes = [_cause("CPE-003")]
    ctx = build_heuristic_consolidation_context(causes, targeted_probe=None)
    out = consolidate_heuristic_root_causes(causes, ctx, targeted_probe=None)
    assert len(out) == 1
    assert out[0].cause_id == "CPE-003"
