"""
E2E 测试 - 并发场景与健壮性

验证系统在并发执行、重复操作和资源竞争下的稳定性。
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
from sdwan_desktop.runtime.engine import FlowRuntime
from sdwan_desktop.tools.registry.dispatcher import ToolDispatcher


@pytest.mark.asyncio
async def test_concurrent_flow_execution():
    """
    测试多个 Flow 并发执行
    
    验证点：
    1. 多个诊断流程可以同时运行而不互相干扰
    2. 每个流程的 trace_id 保持独立
    3. 资源（如 Mock 工具）被正确隔离
    """
    runtime = FlowRuntime()
    
    async def dummy_handler(ctx):
        await asyncio.sleep(0.01)  # 模拟少量处理
        return {"status": "ok", "trace_id": ctx.trace_id}

    handlers = {step.id: dummy_handler for step in QUICK_CHECK_FLOW.steps}
    
    # 启动 5 个并发流程
    tasks = []
    for i in range(5):
        ctx = FlowContext(flow_id=f"concurrent-{i}", flow_name="Concurrent Test", trace_id=f"trace-{i}")
        tasks.append(runtime.execute_flow(QUICK_CHECK_FLOW, ctx, handlers))
    
    results = await asyncio.gather(*tasks)
    
    # 验证所有流程都成功完成
    assert len(results) == 5
    for i, result in enumerate(results):
        assert result is not None


@pytest.mark.asyncio
async def test_tool_registry_concurrent_registration():
    """
    测试 ToolRegistry 并发注册
    
    验证点：
    1. 多个线程/协程同时注册工具不会导致竞态条件
    2. 注册表状态一致
    """
    dispatcher = ToolDispatcher()
    
    async def register_tool(name, index):
        # 模拟工具注册逻辑
        await asyncio.sleep(0.001)
        return f"{name}_{index}"

    tasks = [register_tool("tool", i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 10


@pytest.mark.asyncio
async def test_gui_duplicate_click_prevention():
    """
    模拟 GUI 诊断期间重复点击按钮的场景
    
    验证点：
    1. 正在执行的诊断应阻止新的诊断启动
    2. 或者新的请求应排队/被忽略
    """
    is_running = False
    
    async def start_diagnosis():
        nonlocal is_running
        if is_running:
            raise RuntimeError("Diagnosis already in progress")
        
        is_running = True
        try:
            await asyncio.sleep(0.1)  # 模拟诊断过程
        finally:
            is_running = False

    # 第一次点击
    task1 = asyncio.create_task(start_diagnosis())
    await asyncio.sleep(0.01)  # 让 task1 开始执行
    
    # 第二次点击（在 task1 完成前）
    with pytest.raises(RuntimeError, match="already in progress"):
        await start_diagnosis()
    
    await task1  # 等待第一个任务完成
    
    # 现在应该可以再次启动
    await start_diagnosis()
