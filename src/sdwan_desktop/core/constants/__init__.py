"""
SD-WAN诊断平台 - 常量定义模块

此模块包含系统级常量定义，包括：
- 错误码常量
- 严重程度枚举
- 配置常量
- 系统级阈值
"""

from enum import Enum


class Severity(str, Enum):
    """严重程度枚举"""
    INFO = "info"           # 信息
    WARNING = "warning"     # 警告
    ERROR = "error"         # 错误
    CRITICAL = "critical"   # 严重


class Confidence(str, Enum):
    """置信度枚举"""
    HIGH = "high"           # >90%
    MEDIUM = "medium"       # 60-90%
    LOW = "low"             # 30-60%
    UNCERTAIN = "uncertain" # <30%


class FlowStatus(str, Enum):
    """流程状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProbeProtocol(str, Enum):
    """探测协议枚举"""
    ICMP = "icmp"
    TCP = "tcp"
    UDP = "udp"
    DNS = "dns"
    HTTP = "http"
    HTTPS = "https"


class ProbeStatus(str, Enum):
    """探测状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PARTIAL = "partial"


# 默认配置常量
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRY_COUNT = 2
DEFAULT_MAX_CONCURRENT = 5
DEFAULT_FLOW_TIMEOUT = 300  # 5分钟