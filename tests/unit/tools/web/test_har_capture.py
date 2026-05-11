"""
HAR采集工具单元测试

使用Mock模拟Playwright调用，验证HarCaptureTool的逻辑。
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool


@pytest.fixture
def mock_flow_context():
    """创建模拟的FlowContext"""
    ctx = MagicMock(spec=FlowContext)
    ctx.trace_id = "test-trace-id-123"
    return ctx


@pytest.mark.asyncio
async def test_har_capture_success(mock_flow_context):
    """测试HAR采集成功场景"""
    # Mock PlaywrightAdapter
    with patch("sdwan_desktop.tools.implementations.web.har_capture.PlaywrightAdapter") as MockAdapter:
        mock_adapter_instance = AsyncMock()
        MockAdapter.return_value = mock_adapter_instance
        
        tool = HarCaptureTool()
        request = ToolRequest(
            tool_name="har_capture",
            parameters={
                "url": "https://example.com",
                "headless": True,
                "output_dir": "./test_har_output"
            }
        )
        
        response = await tool.execute(request, mock_flow_context)
        
        assert response.success is True
        assert "har_file_path" in response.data
        assert "screenshot_path" in response.data
        assert mock_adapter_instance.initialize.called
        assert mock_adapter_instance.navigate.called
        assert mock_adapter_instance.screenshot.called
        assert mock_adapter_instance.close.called


@pytest.mark.asyncio
async def test_har_capture_missing_url(mock_flow_context):
    """测试缺少URL参数的情况"""
    tool = HarCaptureTool()
    request = ToolRequest(
        tool_name="har_capture",
        parameters={}
    )
    
    response = await tool.execute(request, mock_flow_context)
    
    assert response.success is False
    assert response.error_code == "VAL_002"


@pytest.mark.asyncio
async def test_har_capture_execution_error(mock_flow_context):
    """测试执行过程中发生异常的情况"""
    with patch("sdwan_desktop.tools.implementations.web.har_capture.PlaywrightAdapter") as MockAdapter:
        mock_adapter_instance = AsyncMock()
        mock_adapter_instance.navigate.side_effect = Exception("Network Error")
        MockAdapter.return_value = mock_adapter_instance
        
        tool = HarCaptureTool()
        request = ToolRequest(
            tool_name="har_capture",
            parameters={"url": "https://example.com"}
        )
        
        response = await tool.execute(request, mock_flow_context)
        
        assert response.success is False
        assert response.error_code == "TOOL_EXEC_ERROR"
        assert mock_adapter_instance.close.called  # 确保即使出错也调用了close
