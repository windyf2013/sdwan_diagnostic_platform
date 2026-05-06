"""
Collector 模块公共 API

导出所有采集器相关类和接口。
"""

from sdwan_desktop.services.collector.base import (
    BaseCollector,
    CollectorConfig,
    CollectorResult,
)
from sdwan_desktop.services.collector.cpe_collector import (
    CpeCollector,
    CpeCollectorConfig,
    CommandExecutionError,
)
from sdwan_desktop.services.collector.device_collector import DeviceCollector

__all__ = [
    "BaseCollector",
    "CollectorConfig",
    "CollectorResult",
    "CpeCollector",
    "CpeCollectorConfig",
    "CommandExecutionError",
    "DeviceCollector",
]
