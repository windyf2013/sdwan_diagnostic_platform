"""
探测相关数据契约模块 - 定义探测目标、结果和指标

遵循 SDWAN_SPEC.md §3.2 探测相关契约
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from .base import BaseContract


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


@dataclass(slots=True)
class ProbeTarget(BaseContract):
    """探测目标定义"""
    
    host: str
    port: Optional[int] = None
    protocol: ProbeProtocol = ProbeProtocol.ICMP
    dns_server: Optional[str] = None          # DNS探测时指定服务器
    count: int = 4                            # 探测次数
    timeout_seconds: int = 30
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProbeMetric:
    """探测指标"""
    
    rtt_min: Optional[float] = None           # 最小RTT(ms)
    rtt_avg: Optional[float] = None           # 平均RTT(ms)
    rtt_max: Optional[float] = None           # 最大RTT(ms)
    rtt_stddev: Optional[float] = None        # RTT标准差
    loss_rate: Optional[float] = None         # 丢包率(0-1)
    ttl: Optional[int] = None                 # TTL值
    resolved_ips: List[str] = field(default_factory=list)  # DNS解析结果
    response_code: Optional[int] = None       # HTTP状态码/DNS响应码


@dataclass(slots=True)
class ProbeResult(BaseContract):
    """单次探测结果"""
    
    target: ProbeTarget
    status: ProbeStatus = ProbeStatus.PENDING
    success: bool = False
    raw_output: Optional[str] = None          # 原始输出(仅内部流转)
    metrics: ProbeMetric = field(default_factory=ProbeMetric)
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    duration_ms: float = 0.0                  # 执行耗时