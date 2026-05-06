"""
基础数据契约模块 - 定义所有数据契约的基类

遵循 SDWAN_SPEC.md §2.1 数据结构规范
使用 dataclass(slots=True) 装饰器
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict
from enum import Enum
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
        
        def _convert_value(obj):
            if hasattr(obj, 'to_json_dict'):
                return obj.to_json_dict()
            elif isinstance(obj, Enum):
                return obj.value
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj

        d = asdict(self)
        # 递归转换特殊类型
        for key, value in d.items():
            if isinstance(value, list):
                d[key] = [_convert_value(item) for item in value]
            else:
                d[key] = _convert_value(value)
                
        return d

    def __repr__(self):
        # 获取所有字段的简要表示，避免输出过长
        items = []
        for field_name in self.__dataclass_fields__:
            val = getattr(self, field_name)
            if isinstance(val, list):
                items.append(f"{field_name}=[{len(val)} items]")
            elif isinstance(val, (str, int, float, bool)) or val is None:
                items.append(f"{field_name}={val}")
            else:
                items.append(f"{field_name}={type(val).__name__}")
        return f"{self.__class__.__name__}({', '.join(items)})"
