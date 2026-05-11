"""
性能基准测试 - 执行耗时

验证各核心流程的执行耗时是否符合预期指标：
- 一键体检 < 30s
- 深度诊断 < 2min
- Waterfall < 45s
- GUI启动 < 3s
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
from sdwan_desktop.flow.definitions.deep_dive import DEEP_DIVE_FLOW
from sdwan_desktop.flow.definitions.waterfall import WATERFALL_FLOW
from sdwan_desktop.runtime.engine import FlowRuntime


@pytest.mark.benchmark(group="execution_time")
def test_quick_check_execution_time(perf_monitor):
    """
    测试一键体检流程执行耗时
    
    目标: < 30s (30000ms)
    """
    import asyncio

    async def run_flow():
        perf_monitor.start()
        
        ctx = FlowContext(flow_id="bench-qc", flow_name="Quick Check Bench", trace_id="bench-001")
        runtime = FlowRuntime()

        # Mock handlers to simulate execution without real network calls
        async def dummy_handler(ctx): return {"status": "ok"}

        handlers = {step.id: dummy_handler for step in QUICK_CHECK_FLOW.steps}
        
        await runtime.execute_flow(QUICK_CHECK_FLOW, ctx, handlers)
        perf_monitor.stop()

    asyncio.run(run_flow())
    
    # 验证耗时：在 Mock 环境下，流程编排本身的开销应极小
    assert perf_monitor.duration_ms < 5000, f"Quick Check took {perf_monitor.duration_ms:.2f}ms"


@pytest.mark.benchmark(group="execution_time")
def test_deep_dive_execution_time(perf_monitor):
    """
    测试深度诊断流程执行耗时
    
    目标: < 2min (120000ms)
    """
    import asyncio

    async def run_flow():
        perf_monitor.start()
        
        ctx = FlowContext(flow_id="bench-dd", flow_name="Deep Dive Bench", trace_id="bench-002")
        runtime = FlowRuntime()

        async def dummy_handler(ctx): return {"status": "ok"}

        handlers = {step.id: dummy_handler for step in DEEP_DIVE_FLOW.steps}
        
        await runtime.execute_flow(DEEP_DIVE_FLOW, ctx, handlers)
        perf_monitor.stop()

    asyncio.run(run_flow())
    
    assert perf_monitor.duration_ms < 10000, f"Deep Dive took {perf_monitor.duration_ms:.2f}ms"


@pytest.mark.benchmark(group="execution_time")
def test_waterfall_execution_time(perf_monitor):
    """
    测试业务监测流程执行耗时
    
    目标: < 45s (45000ms)
    """
    import asyncio

    async def run_flow():
        perf_monitor.start()
        
        ctx = FlowContext(flow_id="bench-wf", flow_name="Waterfall Bench", trace_id="bench-003")
        runtime = FlowRuntime()

        async def dummy_handler(ctx): return {"status": "ok"}

        handlers = {step.id: dummy_handler for step in WATERFALL_FLOW.steps}
        
        await runtime.execute_flow(WATERFALL_FLOW, ctx, handlers)
        perf_monitor.stop()

    asyncio.run(run_flow())
    
    assert perf_monitor.duration_ms < 8000, f"Waterfall took {perf_monitor.duration_ms:.2f}ms"


@pytest.mark.benchmark(group="gui_startup")
def test_gui_startup_time(perf_monitor):
    """
    测试 GUI 应用启动耗时
    
    目标: < 3s (3000ms)
    """
    from PySide6.QtWidgets import QApplication
    import sys
    
    perf_monitor.start()
    
    # 模拟 QApplication 初始化
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        
    perf_monitor.stop()
    
    assert perf_monitor.duration_ms < 2000, f"GUI Startup took {perf_monitor.duration_ms:.2f}ms"
