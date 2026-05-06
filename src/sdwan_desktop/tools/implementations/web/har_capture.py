"""HAR采集工具 - 基于Playwright录制网页HAR文件

遵循 SDWAN_SPEC.md §2.4 工具系统规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.registry.decorator import tool_function
from sdwan_desktop.tools.adapters.playwright_adapter import PlaywrightAdapter

logger = logging.getLogger(__name__)


@tool_function(
    name="har_capture",
    description="使用Playwright录制网页访问的HAR文件，用于性能分析",
    timeout=120,
    retry_count=0,
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "目标URL"},
            "headless": {"type": "boolean", "default": True, "description": "是否无头模式"},
            "timeout": {"type": "integer", "default": 60000, "description": "页面加载超时时间(ms)"},
            "wait_until": {"type": "string", "enum": ["load", "domcontentloaded", "networkidle"], "default": "networkidle"},
            "output_dir": {"type": "string", "description": "输出目录，默认为当前工作目录下的har_output"},
        },
        "required": ["url"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "har_file_path": {"type": "string", "description": "生成的HAR文件路径"},
            "screenshot_path": {"type": "string", "description": "截图文件路径（可选）"},
            "page_load_time_ms": {"type": "number", "description": "页面加载耗时(ms)"},
        },
        "required": ["success", "har_file_path"],
    },
)
class HarCaptureTool:
    """HAR采集工具
    
    通过Playwright启动Chromium浏览器，导航到指定URL并录制HAR文件。
    """
    
    async def execute(self, request: ToolRequest, ctx: FlowContext) -> ToolResponse:
        """执行HAR采集
        
        Args:
            request: 工具请求
            ctx: 流程上下文
            
        Returns:
            ToolResponse: 采集结果
        """
        params = request.parameters
        url = params.get("url")
        headless = params.get("headless", True)
        page_timeout = params.get("timeout", 60000)
        wait_until = params.get("wait_until", "networkidle")
        output_dir = params.get("output_dir", os.path.join(os.getcwd(), "har_output"))

        if not url:
            return ToolResponse(
                success=False,
                error_code="VAL_002",
                error_message="缺少必填参数: url",
                trace_id=ctx.trace_id
            )

        adapter = PlaywrightAdapter()
        har_path = ""
        screenshot_path = ""
        start_time = asyncio.get_event_loop().time()

        try:
            await adapter.initialize(headless=headless)
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            har_filename = f"har_{ctx.trace_id}.har"
            har_path = os.path.join(output_dir, har_filename)
            
            logger.info(f"开始录制HAR: {url}, 输出路径: {har_path}")
            
            await adapter.navigate(url, har_path=har_path, timeout=page_timeout, wait_until=wait_until)
            
            # 可选：截取屏幕快照
            screenshot_filename = f"screenshot_{ctx.trace_id}.png"
            screenshot_path = os.path.join(output_dir, screenshot_filename)
            await adapter.screenshot(screenshot_path)
            
            end_time = asyncio.get_event_loop().time()
            duration_ms = (end_time - start_time) * 1000

            return ToolResponse(
                success=True,
                data={
                    "har_file_path": har_path,
                    "screenshot_path": screenshot_path,
                    "page_load_time_ms": duration_ms,
                },
                trace_id=ctx.trace_id
            )

        except Exception as e:
            logger.error(f"HAR采集失败: {str(e)}", exc_info=True)
            return ToolResponse(
                success=False,
                error_code="TOOL_EXEC_ERROR",
                error_message=f"HAR采集执行失败: {str(e)}",
                trace_id=ctx.trace_id
            )
        finally:
            await adapter.close()
