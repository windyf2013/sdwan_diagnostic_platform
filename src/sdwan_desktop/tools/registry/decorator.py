"""
工具函数装饰器

遵循 SDWAN_SPEC_PATCHES.md PATCH-003: 函数分类改为装饰器
使用装饰器标注函数类型，CI可自动验证
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from .base import ToolMetadata, ToolRegistry

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Callable)


def pure_function(func: T) -> T:
    """标记纯函数装饰器
    
    CI验证：无IO、无副作用、确定性
    遵循 SDWAN_SPEC.md §2.2.3 函数分类标准
    """
    func._spec_type = "pure"
    
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
    
    return wrapper  # type: ignore


def service_function(func: T) -> T:
    """标记服务函数装饰器
    
    CI验证：依赖注入、无直接IO
    遵循 SDWAN_SPEC.md §2.2.3 函数分类标准
    """
    func._spec_type = "service"
    
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
    
    return wrapper  # type: ignore


def orchestrator_function(func: T) -> T:
    """标记编排函数装饰器
    
    CI验证：无业务逻辑、状态可回放
    遵循 SDWAN_SPEC.md §2.2.3 函数分类标准
    """
    func._spec_type = "orchestrator"
    
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
    
    return wrapper  # type: ignore


def tool_function(
    name: str,
    description: str = "",
    timeout: int = 30,
    retry_count: int = 0,
    required_permissions: Optional[list[str]] = None,
    input_schema: Optional[Dict[str, Any]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
) -> Callable[[Type], Type]:
    """工具函数装饰器 - 自动注册工具到ToolRegistry
    
    遵循 SDWAN_SPEC_PATCHES.md PATCH-003
    遵循 SDWAN_SPEC.md §2.4.1 工具约束
    
    Args:
        name: 工具名称，唯一标识
        description: 工具描述
        timeout: 默认超时时间（秒）
        retry_count: 默认重试次数
        required_permissions: 所需权限列表
        input_schema: 输入参数schema
        output_schema: 输出结果schema
    """
    
    def decorator(tool_class: Type) -> Type:
        """装饰器实现"""
        
        # 1. 标记函数类型
        tool_class._spec_type = "tool"
        tool_class._tool_name = name
        
        # 2. 创建元数据
        metadata = ToolMetadata(
            name=name,
            description=description,
            version="1.0.0",
            timeout_seconds=timeout,
            retry_count=retry_count,
            required_permissions=required_permissions or [],
            input_schema=input_schema,
            output_schema=output_schema,
        )
        
        # 3. 注册到ToolRegistry
        registry = ToolRegistry()
        registry.register(tool_class, metadata)
        
        logger.info(f"工具装饰器注册: {name} -> {tool_class.__name__}")
        
        # 4. 添加工具元数据到类属性
        tool_class._tool_metadata = metadata
        
        # 5. 确保类有execute方法
        if not hasattr(tool_class, "execute"):
            raise TypeError(
                f"工具类 {tool_class.__name__} 必须实现 execute 方法"
            )
        
        # 6. 验证execute方法签名
        execute_method = getattr(tool_class, "execute")
        if not callable(execute_method):
            raise TypeError(
                f"工具类 {tool_class.__name__} 的 execute 必须是可调用方法"
            )
        
        return tool_class
    
    return decorator


def get_function_type(func: Callable) -> Optional[str]:
    """获取函数类型
    
    Args:
        func: 函数或方法
        
    Returns:
        函数类型: "pure", "service", "tool", "orchestrator" 或 None
    """
    return getattr(func, "_spec_type", None)


def is_pure_function(func: Callable) -> bool:
    """检查是否为纯函数
    
    Args:
        func: 函数或方法
        
    Returns:
        是否为纯函数
    """
    return get_function_type(func) == "pure"


def is_service_function(func: Callable) -> bool:
    """检查是否为服务函数
    
    Args:
        func: 函数或方法
        
    Returns:
        是否为服务函数
    """
    return get_function_type(func) == "service"


def is_tool_function(func: Callable) -> bool:
    """检查是否为工具函数
    
    Args:
        func: 函数或方法
        
    Returns:
        是否为工具函数
    """
    return get_function_type(func) == "tool"


def is_orchestrator_function(func: Callable) -> bool:
    """检查是否为编排函数
    
    Args:
        func: 函数或方法
        
    Returns:
        是否为编排函数
    """
    return get_function_type(func) == "orchestrator"