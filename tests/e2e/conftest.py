"""
端到端测试共享 Fixtures

提供 Mock 注册表、示例 FlowContext 和临时目录等通用资源。
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.registry.dispatcher import ToolDispatcher


@pytest.fixture
def temp_dir():
    """提供一个临时目录用于存储测试生成的报告或文件"""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)


@pytest.fixture
def sample_flow_context():
    """创建一个标准的测试用 FlowContext"""
    ctx = FlowContext(
        flow_id="test-e2e-flow",
        flow_name="E2E Test",
        trace_id="e2e-trace-001"
    )
    return ctx


@pytest.fixture
def mock_tool_dispatcher():
    """Mock ToolDispatcher，避免真实网络调用"""
    dispatcher = MagicMock(spec=ToolDispatcher)
    
    async def mock_dispatch(tool_name: str, request, ctx):
        # 默认返回成功响应
        from sdwan_desktop.tools.registry.base import ToolResponse
        return ToolResponse(
            success=True,
            data={"mocked": True, "tool": tool_name},
            trace_id=ctx.trace_id
        )
    
    dispatcher.dispatch = AsyncMock(side_effect=mock_dispatch)
    return dispatcher


@pytest.fixture
def mock_registry():
    """Mock 工具注册表"""
    registry = MagicMock()
    registry.get_tool.return_value = MagicMock()
    return registry
