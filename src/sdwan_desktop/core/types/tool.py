"""
工具系统数据契约 - 定义ToolRequest和ToolResponse

遵循 SDWAN_SPEC.md §2.4 工具系统规范
使用 dataclass(slots=True) 装饰器
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from .base import BaseContract


@dataclass(slots=True, init=False)
class ToolRequest(BaseContract):
    """工具请求契约
    
    所有工具调用的统一输入格式
    遵循 SDWAN_SPEC.md §2.4.1 工具约束
    """
    
    # 注意：tool_name没有默认值，必须出现在所有带默认值字段之前
    tool_name: str
    """工具名称，必须与ToolRegistry中注册的名称一致"""
    
    # 以下字段都有默认值
    parameters: Dict[str, Any] = field(default_factory=dict)
    """工具参数，键值对形式"""
    
    timeout_seconds: Optional[int] = None
    """超时时间（秒），覆盖工具默认超时"""
    
    retry_count: Optional[int] = None
    """重试次数，覆盖工具默认重试策略"""
    
    context: Dict[str, Any] = field(default_factory=dict)
    """执行上下文，包含trace_id等元信息"""
    
    def __init__(self, tool_name: str, parameters: Dict[str, Any] = None, 
                 timeout_seconds: Optional[int] = None, retry_count: Optional[int] = None,
                 context: Dict[str, Any] = None, trace_id: Optional[str] = None):
        """手动定义构造函数以解决字段顺序问题
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            timeout_seconds: 超时时间（秒）
            retry_count: 重试次数
            context: 执行上下文
            trace_id: 追踪ID，如果提供则使用该值，否则自动生成
        """
        # 不要调用super().__init__()，因为使用了@dataclass(slots=True, init=False)
        # 直接初始化BaseContract的字段
        import uuid
        from datetime import datetime, timezone
        
        self.id = str(uuid.uuid4())
        self.trace_id = trace_id or str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc).isoformat()
        
        self.tool_name = tool_name
        self.parameters = parameters or {}
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.context = context or {}
    
    def to_json_dict(self) -> Dict[str, Any]:
        """转换为JSON可序列化字典"""
        from dataclasses import asdict
        
        def _convert_value(obj):
            if hasattr(obj, 'to_json_dict'):
                return obj.to_json_dict()
            elif isinstance(obj, Enum):
                return obj.value
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj
        
        # 使用asdict获取所有字段，然后添加额外字段
        base_dict = asdict(self)
        
        # 递归转换特殊类型
        for key, value in base_dict.items():
            if isinstance(value, list):
                base_dict[key] = [_convert_value(item) for item in value]
            else:
                base_dict[key] = _convert_value(value)
        
        return base_dict


@dataclass(slots=True)
class ToolResponse(BaseContract):
    """工具响应契约
    
    所有工具调用的统一输出格式
    遵循 SDWAN_SPEC.md §2.4.1 工具约束
    """
    
    success: bool = False
    """执行是否成功"""
    
    data: Optional[Dict[str, Any]] = None
    """执行结果数据，成功时返回"""
    
    error_code: Optional[str] = None
    """错误代码，失败时返回（遵循SDWAN_SPEC.md §2.5错误体系）"""
    
    error_message: Optional[str] = None
    """错误描述，失败时返回"""
    
    duration_ms: float = 0.0
    """执行耗时（毫秒）"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """元数据，如原始输出、警告信息等"""
    
    def to_json_dict(self) -> Dict[str, Any]:
        """转换为JSON可序列化字典"""
        def _convert_value(obj):
            if hasattr(obj, 'to_json_dict'):
                return obj.to_json_dict()
            elif isinstance(obj, Enum):
                return obj.value
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj
            
        # 直接使用asdict获取所有字段，避免super()调用的MRO问题
        base_dict = asdict(self)
            
        # 递归转换特殊类型
        for key, value in base_dict.items():
            if isinstance(value, list):
                base_dict[key] = [_convert_value(item) for item in value]
            else:
                base_dict[key] = _convert_value(value)
            
        return base_dict