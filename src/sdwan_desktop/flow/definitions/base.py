"""
流程定义基础类
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass(slots=True)
class RetryPolicy:
    """重试策略"""
    max_attempts: int = 3
    backoff_seconds: float = 1.0


@dataclass(slots=True)
class StepDefinition:
    """步骤定义"""
    id: str
    name: str
    description: str
    handler: str
    depends_on: List[str] = field(default_factory=list)
    timeout_seconds: int = 60
    retry_policy: Optional[RetryPolicy] = None


@dataclass(slots=True)
class FlowDefinition:
    """流程定义"""
    id: str
    name: str
    version: str
    description: str
    steps: List[StepDefinition] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
