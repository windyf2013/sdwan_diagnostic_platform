"""工具调度器 - 唯一工具调用入口"""

import asyncio
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
import uuid

from ..core.errors.tool import ToolError, ToolTimeoutError
from ..core.types.context import Context
from .base import ToolRegistry, ToolMetadata


@dataclass
class ToolRequest:
    """工具请求"""
    tool_name: str
    params: Dict[str, Any]
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timeout_seconds: Optional[int] = None


@dataclass
class ToolResponse:
    """工具响应"""
    success: bool
    data: Dict[str, Any]
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    duration_ms: float = 0.0


class ToolDispatcher:
    """工具调度器 - 唯一工具调用入口"""
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry()
    
    async def dispatch(
        self,
        request: ToolRequest,
        ctx: Context
    ) -> ToolResponse:
        """调度工具执行"""
        import time
        start_time = time.time()
        
        tool_class = self.registry.get_tool(request.tool_name)
        if not tool_class:
            raise ToolError(
                error_code="TOOL_001",
                message=f"工具 {request.tool_name} 未注册",
                context={"tool_name": request.tool_name},
                trace_id=ctx.trace_id
            )
        
        metadata = self.registry.get_metadata(request.tool_name)
        
        # 参数校验
        self._validate_request(request, metadata)
        
        # 执行工具 (支持超时和重试)
        try:
            result = await self._execute_with_retry(
                tool_class, request, ctx, metadata
            )
            
            return ToolResponse(
                success=True,
                data=result,
                trace_id=ctx.trace_id,
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except ToolTimeoutError as e:
            return ToolResponse(
                success=False,
                data={},
                error_code=e.error_code,
                error_message=e.message,
                trace_id=ctx.trace_id,
                duration_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return ToolResponse(
                success=False,
                data={},
                error_code="TOOL_002",
                error_message=f"工具执行失败: {str(e)}",
                trace_id=ctx.trace_id,
                duration_ms=(time.time() - start_time) * 1000
            )
    
    async def _execute_with_retry(
        self,
        tool_class: Type,
        request: ToolRequest,
        ctx: Context,
        metadata: ToolMetadata
    ) -> Dict[str, Any]:
        """带重试的执行"""
        last_error = None
        
        timeout = request.timeout_seconds or metadata.timeout_seconds
        
        for attempt in range(metadata.retry_count + 1):
            try:
                tool_instance = tool_class()
                result = await asyncio.wait_for(
                    tool_instance.execute(request, ctx),
                    timeout=timeout
                )
                return result
            except asyncio.TimeoutError:
                last_error = ToolTimeoutError(
                    error_code="TOOL_003",
                    message=f"工具 {metadata.name} 执行超时",
                    context={"attempt": attempt + 1, "timeout_seconds": timeout},
                    trace_id=ctx.trace_id
                )
            except Exception as e:
                last_error = e
        
        if isinstance(last_error, ToolError):
            raise last_error
        else:
            raise ToolError(
                error_code="TOOL_002",
                message=f"工具 {metadata.name} 执行失败",
                context={"error": str(last_error)},
                trace_id=ctx.trace_id
            )
    
    def _validate_request(
        self,
        request: ToolRequest,
        metadata: ToolMetadata
    ) -> None:
        """验证请求参数"""
        # TODO: 实现基于schema的验证
        pass