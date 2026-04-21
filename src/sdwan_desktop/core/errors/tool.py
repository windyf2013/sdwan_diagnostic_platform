"""
工具相关错误类
"""

from typing import Any, Dict, Optional
from .base import BaseError


class ToolError(BaseError):
    """外部工具调用错误"""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        # 确保错误码前缀为 TOOL_
        if not error_code.startswith("TOOL_"):
            error_code = f"TOOL_{error_code}"
        
        super().__init__(
            error_code=error_code,
            message=message,
            context=context,
            trace_id=trace_id
        )


class ToolTimeoutError(ToolError):
    """工具执行超时错误"""
    
    def __init__(
        self,
        tool_name: str,
        timeout_seconds: int,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            error_code="TOOL_TIMEOUT",
            message=f"工具 {tool_name} 执行超时 ({timeout_seconds}秒)",
            context={
                "tool_name": tool_name,
                "timeout_seconds": timeout_seconds,
                **(context or {})
            },
            trace_id=trace_id
        )


class ToolConnectionError(ToolError):
    """工具连接错误"""
    
    def __init__(
        self,
        tool_name: str,
        target: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            error_code="TOOL_CONNECTION",
            message=f"工具 {tool_name} 连接失败: {target} - {reason}",
            context={
                "tool_name": tool_name,
                "target": target,
                "reason": reason,
                **(context or {})
            },
            trace_id=trace_id
        )