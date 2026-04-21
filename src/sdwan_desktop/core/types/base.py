"""
基础数据契约模块 - 定义所有数据契约的基类

遵循 SDWAN_SPEC.md §2.1 数据结构规范
使用 dataclass(slots=True) 装饰器
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict
import uuid


def utc_now_iso() -> str:
    """返回UTC时间ISO格式字符串"""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class BaseContract:
    """所有数据契约的基类"""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=utc_now_iso)

    def to_json_dict(self) -> Dict[str, Any]:
        """转换为JSON可序列化字典"""
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
        }