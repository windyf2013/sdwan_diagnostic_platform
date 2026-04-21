"""
工具注册中心模块

遵循 SDWAN_SPEC.md §2.8 导入导出与模块边界规范
显式导出公共API，通过 __all__ 声明对外符号集合
"""

from .base import ToolMetadata, ToolRegistry, ToolDispatcher
from .decorator import (
    pure_function,
    service_function,
    tool_function,
    orchestrator_function,
    get_function_type,
    is_pure_function,
    is_service_function,
    is_tool_function,
    is_orchestrator_function,
)

__all__ = [
    # 基础类
    "ToolMetadata",
    "ToolRegistry",
    "ToolDispatcher",
    
    # 装饰器
    "pure_function",
    "service_function",
    "tool_function",
    "orchestrator_function",
    
    # 工具函数检查
    "get_function_type",
    "is_pure_function",
    "is_service_function",
    "is_tool_function",
    "is_orchestrator_function",
]

# 创建全局单例实例
tool_registry = ToolRegistry()
tool_dispatcher = ToolDispatcher(tool_registry)

# 导出单例实例
__all__.extend(["tool_registry", "tool_dispatcher"])