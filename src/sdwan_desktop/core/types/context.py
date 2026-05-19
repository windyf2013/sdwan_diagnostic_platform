"""
Flow Context 类型定义
用于流程执行上下文
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import uuid


@dataclass(slots=True)
class FlowContext:
    """流程执行上下文。

    步骤间通过 ``metadata`` 传递产物；各流在 ``FlowDefinition.config['shared_context_keys']``
    中声明约定键名（由 ``FlowRuntime`` 在 DEBUG 下提示缺失项），具体值类型由各步骤保证。
    """
    
    flow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    flow_name: str = "default_flow"
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    step_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())
        if not self.flow_id:
            self.flow_id = str(uuid.uuid4())
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文数据"""
        return self.metadata.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """设置上下文数据"""
        self.metadata[key] = value


# 保持向后兼容
Context = FlowContext