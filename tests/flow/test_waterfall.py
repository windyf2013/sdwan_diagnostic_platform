"""
Waterfall Flow 单元测试

验证流程定义的完整性和步骤依赖关系。
"""

import pytest
from sdwan_desktop.flow.definitions.waterfall import WATERFALL_FLOW


def test_waterfall_flow_structure():
    """测试 Waterfall Flow 基本结构"""
    assert WATERFALL_FLOW.id == "waterfall-analysis-v1"
    assert WATERFALL_FLOW.name == "Web性能瀑布流分析"
    assert len(WATERFALL_FLOW.steps) == 5


def test_waterfall_flow_steps():
    """测试步骤定义"""
    step_ids = [s.id for s in WATERFALL_FLOW.steps]
    expected_steps = [
        "step-har-capture",
        "step-har-parse",
        "step-perf-analyze",
        "step-rule-check",
        "step-report-generate"
    ]
    assert step_ids == expected_steps


def test_waterfall_flow_dependencies():
    """测试步骤依赖关系"""
    steps = {s.id: s for s in WATERFALL_FLOW.steps}
    
    # HAR解析依赖于采集
    assert "step-har-capture" in steps["step-har-parse"].depends_on
    
    # 性能分析和规则匹配都依赖于解析
    assert "step-har-parse" in steps["step-perf-analyze"].depends_on
    assert "step-har-parse" in steps["step-rule-check"].depends_on
    
    # 报告生成依赖于分析和规则匹配
    assert "step-perf-analyze" in steps["step-report-generate"].depends_on
    assert "step-rule-check" in steps["step-report-generate"].depends_on
