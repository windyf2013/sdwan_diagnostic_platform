"""
基础错误类定义
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import uuid


@dataclass(slots=True)
class BaseError(Exception):
    """所有错误的基类"""
    
    error_code: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __init__(
        self,
        error_code: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        self.error_code = error_code
        self.message = message
        self.context = context or {}
        self.trace_id = trace_id or str(uuid.uuid4())
        super().__init__(message)
    
    def __str__(self) -> str:
        """返回格式化错误信息"""
        return f"[{self.error_code}] {self.message} (trace_id: {self.trace_id})"
    
    def to_dict(self) -> Dict[str, Any]:
        """返回可序列化字典"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "trace_id": self.trace_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseError":
        """从字典创建错误实例"""
        return cls(
            error_code=data["error_code"],
            message=data["message"],
            context=data.get("context", {}),
            trace_id=data.get("trace_id")
        )