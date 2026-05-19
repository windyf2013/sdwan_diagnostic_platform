"""业务诊断流程定义校验。"""

from sdwan_desktop.flow.definitions.business_diagnose import BUSINESS_DIAGNOSE_FLOW


def test_business_diagnose_flow_steps():
    assert BUSINESS_DIAGNOSE_FLOW.id == "business-diagnose-v1"
    assert len(BUSINESS_DIAGNOSE_FLOW.steps) == 6
    ids = [s.id for s in BUSINESS_DIAGNOSE_FLOW.steps]
    assert ids[0] == "step-pc-collect"
    assert "step-overlay-policy-flow" in ids
    assert "step-validate-joint-prereq" in ids


def test_business_overlay_depends_on_joint():
    steps = {s.id: s for s in BUSINESS_DIAGNOSE_FLOW.steps}
    assert "step-joint-cpe-topology" in steps["step-overlay-policy-flow"].depends_on
