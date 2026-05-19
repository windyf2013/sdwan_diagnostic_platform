"""
深度诊断流程集成测试

验证 DeepDive Flow 的定义完整性及步骤依赖关系。
"""

import pytest
from sdwan_desktop.flow.definitions.deep_dive import DEEP_DIVE_FLOW


class TestDeepDiveFlow:

    def test_flow_definition_exists(self):
        """测试流程定义是否存在且 ID 正确"""
        assert DEEP_DIVE_FLOW is not None
        assert DEEP_DIVE_FLOW.id == "deep-dive-v1"
        assert DEEP_DIVE_FLOW.name == "深度诊断"

    def test_flow_steps_count(self):
        """测试流程步骤数量是否符合预期 (9个步骤)"""
        assert len(DEEP_DIVE_FLOW.steps) == 9

    def test_step_dependencies(self):
        """测试关键步骤的依赖关系"""
        steps = {s.id: s for s in DEEP_DIVE_FLOW.steps}
        
        # CPE 采集应依赖于 PC 采集和 CPE 连接
        assert "step-pc-collect" in steps["step-cpe-collect"].depends_on
        
        # 拓扑构建应依赖于 PC 和 CPE 采集完成
        assert "step-pc-collect" in steps["step-topology-build"].depends_on
        assert "step-cpe-collect" in steps["step-topology-build"].depends_on

        assert "step-topology-build" in steps["step-biz-probe"].depends_on
        assert "step-biz-probe" in steps["step-cpe-post-probe"].depends_on
        assert "step-cpe-post-probe" in steps["step-overlay-policy-flow"].depends_on

        # 根因分析应依赖于拓扑构建、拓扑后探测与 Overlay 证据链步骤
        assert "step-topology-build" in steps["step-root-cause"].depends_on
        assert "step-cpe-post-probe" in steps["step-root-cause"].depends_on
        assert "step-overlay-policy-flow" in steps["step-root-cause"].depends_on

    def test_step_handlers_defined(self):
        """测试所有步骤是否都定义了处理器路径"""
        for step in DEEP_DIVE_FLOW.steps:
            assert step.handler, f"Step {step.id} has no handler defined"

    def test_flow_config(self):
        """测试流程配置参数"""
        assert DEEP_DIVE_FLOW.config["continue_on_error"] is False
        assert DEEP_DIVE_FLOW.config["save_snapshots"] is True
