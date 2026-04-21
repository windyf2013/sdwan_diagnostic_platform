"""
系统相关错误类
"""

from typing import Any, Dict, Optional
from .base import BaseError


class SystemError(BaseError):
    """系统错误"""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            error_code=error_code,
            message=message,
            context=context,
            trace_id=trace_id
        )


class ResourceError(SystemError):
    """资源不足错误"""
    
    def __init__(
        self,
        resource_type: str,
        required: str,
        available: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            error_code="SYS_001",
            message=f"系统资源不足: {resource_type} (需要: {required}, 可用: {available})",
            context={
                "resource_type": resource_type,
                "required": required,
                "available": available,
                **(context or {})
            },
            trace_id=trace_id
        )


class PermissionError(SystemError):
    """权限不足错误"""
    
    def __init__(
        self,
        operation: str,
        required_permission: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            error_code="SYS_002",
            message=f"权限不足: 无法执行 {operation} (需要权限: {required_permission})",
            context={
                "operation": operation,
                "required_permission": required_permission,
                **(context or {})
            },
            trace_id=trace_id
        )