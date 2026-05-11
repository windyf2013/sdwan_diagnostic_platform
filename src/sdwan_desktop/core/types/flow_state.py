"""
流程状态与步骤快照定义
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class FlowStatus(str, Enum):
    """流程状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RETRYING = "retrying"


class StepStatus(str, Enum):
    """步骤状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


@dataclass(slots=True)
class StepSnapshot:
    """步骤执行快照"""
    step_id: str
    name: str
    status: FlowStatus
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0

    def is_completed(self) -> bool:
        return self.status in [FlowStatus.COMPLETED, FlowStatus.FAILED]

    def is_successful(self) -> bool:
        return self.status == FlowStatus.COMPLETED
