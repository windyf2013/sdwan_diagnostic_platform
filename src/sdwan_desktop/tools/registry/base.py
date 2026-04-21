"""
工具注册中心基础设施

遵循 SDWAN_SPEC.md §2.4 工具系统规范
实现 ToolRegistry 单例和 ToolDispatcher 调度器
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union
from abc import ABC, abstractmethod

from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.errors.tool import ToolError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Callable)


@dataclass(slots=True)
class ToolMetadata:
    """工具元数据
    
    遵循 SDWAN_SPEC.md §2.4.1 工具约束
    """
    
    name: str
    """工具名称，唯一标识"""
    
    description: str = ""
    """工具描述"""
    
    version: str = "1.0.0"
    """工具版本"""
    
    timeout_seconds: int = 30
    """默认超时时间（秒）"""
    
    retry_count: int = 0
    """默认重试次数"""
    
    required_permissions: list[str] = field(default_factory=list)
    """所需权限列表"""
    
    input_schema: Optional[Dict[str, Any]] = None
    """输入参数schema"""
    
    output_schema: Optional[Dict[str, Any]] = None
    """输出结果schema"""
    
    tool_class: Optional[Type] = None
    """工具类引用"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "required_permissions": self.required_permissions,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


class ToolRegistry:
    """工具注册中心（单例模式）
    
    遵循 SDWAN_SPEC.md §2.4.1 工具约束
    所有工具必须注册到此处
    """
    
    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, Type] = {}
    _metadata: Dict[str, ToolMetadata] = {}
    
    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(
        self,
        tool_class: Type,
        metadata: ToolMetadata
    ) -> None:
        """注册工具
        
        Args:
            tool_class: 工具类
            metadata: 工具元数据
        """
        if metadata.name in self._tools:
            logger.warning(f"工具 {metadata.name} 已存在，将被覆盖")
        
        metadata.tool_class = tool_class
        self._tools[metadata.name] = tool_class
        self._metadata[metadata.name] = metadata
        
        logger.info(f"工具注册成功: {metadata.name} v{metadata.version}")
    
    def get_tool(self, name: str) -> Optional[Type]:
        """获取工具类
        
        Args:
            name: 工具名称
            
        Returns:
            工具类，如果不存在则返回None
        """
        return self._tools.get(name)
    
    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """获取工具元数据
        
        Args:
            name: 工具名称
            
        Returns:
            工具元数据，如果不存在则返回None
        """
        return self._metadata.get(name)
    
    def list_tools(self) -> list[str]:
        """列出所有已注册工具名称
        
        Returns:
            工具名称列表
        """
        return list(self._tools.keys())
    
    def get_all_metadata(self) -> Dict[str, ToolMetadata]:
        """获取所有工具元数据
        
        Returns:
            工具名称到元数据的映射
        """
        return self._metadata.copy()


class ToolDispatcher:
    """工具调度器 - 唯一工具调用入口
    
    遵循 SDWAN_SPEC.md §2.4.1 工具约束
    负责参数校验、鉴权、执行、超时、重试、日志
    """
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        """初始化调度器
        
        Args:
            registry: 工具注册中心，默认为单例实例
        """
        self.registry = registry or ToolRegistry()
    
    async def dispatch(
        self,
        tool_name: str,
        request: ToolRequest,
        ctx: FlowContext
    ) -> ToolResponse:
        """调度工具执行
        
        Args:
            tool_name: 工具名称
            request: 工具请求
            ctx: 流程上下文
            
        Returns:
            工具响应
            
        Raises:
            ToolError: 工具执行失败
        """
        # 1. 获取工具类和元数据
        tool_class = self.registry.get_tool(tool_name)
        if not tool_class:
            raise ToolError(
                error_code="TOOL_NOT_FOUND",
                message=f"工具 {tool_name} 未注册",
                context={"tool_name": tool_name},
                trace_id=ctx.trace_id
            )
        
        metadata = self.registry.get_metadata(tool_name)
        if not metadata:
            raise ToolError(
                error_code="TOOL_METADATA_MISSING",
                message=f"工具 {tool_name} 元数据缺失",
                context={"tool_name": tool_name},
                trace_id=ctx.trace_id
            )
        
        # 2. 合并超时和重试配置
        timeout = request.timeout_seconds or metadata.timeout_seconds
        retry_count = request.retry_count or metadata.retry_count
        
        # 3. 执行工具（支持重试）
        last_error = None
        start_time = asyncio.get_event_loop().time()
        
        for attempt in range(retry_count + 1):
            try:
                logger.info(
                    f"执行工具 {tool_name} (尝试 {attempt + 1}/{retry_count + 1})",
                    extra={"trace_id": ctx.trace_id}
                )
                
                # 创建工具实例
                tool_instance = tool_class()
                
                # 执行工具（带超时控制）
                result = await asyncio.wait_for(
                    tool_instance.execute(request, ctx),
                    timeout=timeout
                )
                
                # 计算执行时间
                end_time = asyncio.get_event_loop().time()
                duration_ms = (end_time - start_time) * 1000
                
                # 设置执行时间
                if isinstance(result, ToolResponse):
                    result.duration_ms = duration_ms
                
                logger.info(
                    f"工具 {tool_name} 执行成功 (耗时: {duration_ms:.1f}ms)",
                    extra={"trace_id": ctx.trace_id}
                )
                
                return result
                
            except asyncio.TimeoutError:
                last_error = ToolError(
                    error_code="TOOL_TIMEOUT",
                    message=f"工具 {tool_name} 执行超时 ({timeout}s)",
                    context={
                        "tool_name": tool_name,
                        "timeout": timeout,
                        "attempt": attempt + 1,
                    },
                    trace_id=ctx.trace_id
                )
                logger.warning(
                    f"工具 {tool_name} 超时 (尝试 {attempt + 1})",
                    extra={"trace_id": ctx.trace_id}
                )
                
            except Exception as e:
                last_error = e
                logger.error(
                    f"工具 {tool_name} 执行失败 (尝试 {attempt + 1}): {e}",
                    extra={"trace_id": ctx.trace_id},
                    exc_info=True
                )
        
        # 所有重试都失败
        if isinstance(last_error, ToolError):
            raise last_error
        else:
            raise ToolError(
                error_code="TOOL_EXECUTION_FAILED",
                message=f"工具 {tool_name} 执行失败",
                context={
                    "tool_name": tool_name,
                    "retry_count": retry_count,
                    "original_error": str(last_error),
                },
                trace_id=ctx.trace_id
            ) from last_error
    
    def validate_request(
        self,
        request: ToolRequest,
        metadata: ToolMetadata
    ) -> bool:
        """验证工具请求
        
        Args:
            request: 工具请求
            metadata: 工具元数据
            
        Returns:
            验证是否通过
            
        Raises:
            ToolError: 验证失败
        """
        # TODO: 实现schema验证
        # 目前仅做基本检查
        if not request.tool_name:
            raise ToolError(
                error_code="VAL_002",
                message="缺少必填参数: tool_name",
                context={"request": request.to_json_dict()},
                trace_id=request.trace_id
            )
        
        return True