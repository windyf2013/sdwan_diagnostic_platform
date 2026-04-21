"""
流程编排相关错误类
"""

from typing import Any, Dict, Optional
from .base import BaseError


class FlowError(BaseError):
    """编排与状态迁移错误"""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        # 确保错误码前缀为 FLOW_
        if not error_code.startswith("FLOW_"):
            error_code = f"FLOW_{error_code}"
        
        super().__init__(
            error_code=error_code,
            message=message,
            context=context,
            trace_id=trace_id
        )


class FlowStateError(FlowError):
    """流程状态错误"""
    
    def __init__(
        self,
        flow_name: str,
        current_state: str,
        expected_state: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            error_code="FLOW_STATE",
            message=f"流程 {flow_name} 状态错误: 当前 {current_state}, 期望 {expected_state}",
            context={
                "flow_name": flow_name,
                "current_state": current_state,
                "expected_state": expected_state,
                **(context or {})
            },
            trace_id=trace_id
        )


class FlowTimeoutError(FlowError):
    """流程超时错误"""
    
    def __init__(
        self,
        flow_name: str,
        timeout_seconds: int,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            error_code="FLOW_TIMEOUT",
            message=f"流程 {flow_name} 执行超时 ({timeout_seconds}秒)",
            context={
                "flow_name": flow_name,
                "timeout_seconds": timeout_seconds,
                **(context or {})
            },
            trace_id=trace_id
        )