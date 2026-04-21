"""
验证相关错误类
"""

from typing import Any, Dict, Optional
from .base import BaseError


class ValidationError(BaseError):
    """输入与契约校验错误"""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        # 确保错误码前缀为 VAL_
        if not error_code.startswith("VAL_"):
            error_code = f"VAL_{error_code}"
        
        super().__init__(
            error_code=error_code,
            message=message,
            context=context,
            trace_id=trace_id
        )