"""
严重程度常量定义模块

遵循 SDWAN_SPEC.md §3.3 诊断相关契约
"""

from enum import Enum
from typing import Dict, List
from ..types.diagnosis import Severity


# 严重程度中文映射
SEVERITY_CHINESE_MAP: Dict[Severity, str] = {
    Severity.INFO: "信息",
    Severity.WARNING: "警告",
    Severity.ERROR: "错误",
    Severity.CRITICAL: "严重",
}

# 严重程度颜色映射（用于HTML报告）
SEVERITY_COLOR_MAP: Dict[Severity, str] = {
    Severity.INFO: "#2196f3",      # 蓝色
    Severity.WARNING: "#ff9800",   # 橙色
    Severity.ERROR: "#f44336",     # 红色
    Severity.CRITICAL: "#d32f2f",  # 深红色
}

# 严重程度排序（从低到高）
SEVERITY_ORDER: List[Severity] = [
    Severity.INFO,
    Severity.WARNING,
    Severity.ERROR,
    Severity.CRITICAL,
]

# 严重程度权重（用于计算综合严重程度）
SEVERITY_WEIGHTS: Dict[Severity, int] = {
    Severity.INFO: 1,
    Severity.WARNING: 2,
    Severity.ERROR: 3,
    Severity.CRITICAL: 4,
}

# 严重程度阈值配置
SEVERITY_THRESHOLDS = {
    "gateway_rtt_warning_ms": 100,
    "gateway_rtt_critical_ms": 500,
    "gateway_loss_warning_pct": 5,
    "gateway_loss_critical_pct": 20,
    "dns_timeout_ms": 2000,
    "dns_slow_ms": 500,
    "international_loss_warning_pct": 10,
    "international_loss_critical_pct": 30,
}