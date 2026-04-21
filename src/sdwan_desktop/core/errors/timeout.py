"""
超时相关错误类
"""

from typing import Any, Dict, Optional
from .base import BaseError


class TimeoutError(BaseError):
    """超时错误"""
    
    def __init__(
        self,
        operation: str,
        timeout_seconds: int,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            error_code="TIME_001",
            message=f"操作 {operation} 超时 ({timeout_seconds}秒)",
            context={
                "operation": operation,
                "timeout_seconds": timeout_seconds,
                **(context or {})
            },
            trace_id=trace_id
        )