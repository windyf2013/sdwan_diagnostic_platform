"""
采集器基类

定义采集器的抽象接口和通用数据结构
遵循 SDWAN_SPEC.md §2.4 工具系统规范
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.context import FlowContext

logger = logging.getLogger(__name__)


@dataclass
class CollectorConfig:
    """采集器配置"""
    device_type: str = "generic"
    """设备类型"""
    timeout_seconds: int = 60
    """采集超时时间"""
    retry_count: int = 1
    """重试次数"""
    collect_interval: int = 300
    """采集间隔（秒）"""
    enable_parallel: bool = True
    """是否启用并行采集"""
    max_workers: int = 5
    """最大并行数"""


@dataclass
class CollectorResult:
    """采集结果"""
    success: bool = False
    """是否成功"""
    data: Dict[str, Any] = field(default_factory=dict)
    """采集的数据"""
    error_message: Optional[str] = None
    """错误信息"""
    duration_ms: float = 0.0
    """采集耗时"""
    collected_items: List[str] = field(default_factory=list)
    """已采集的项目列表"""


class BaseCollector(ABC):
    """采集器基类
    
    所有设备采集器必须继承此类
    """
    
    def __init__(self, config: Optional[CollectorConfig] = None):
        """初始化采集器
        
        Args:
            config: 采集器配置
        """
        self.config = config or CollectorConfig()
    
    @abstractmethod
    async def collect(self, ctx: FlowContext) -> CollectorResult:
        """执行采集
        
        Args:
            ctx: 流程上下文
            
        Returns:
            采集结果
        """
        ...
    
    @abstractmethod
    async def validate(self, ctx: FlowContext) -> bool:
        """验证采集器配置是否有效
        
        Args:
            ctx: 流程上下文
            
        Returns:
            配置是否有效
        """
        ...
    
    def get_supported_items(self) -> List[str]:
        """获取支持采集的项目列表
        
        Returns:
            支持的项目名称列表
        """
        return []
