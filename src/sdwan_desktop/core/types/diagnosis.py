"""
诊断相关数据契约模块 - 定义诊断结果、根因分析和建议

遵循 SDWAN_SPEC.md §3.3 诊断相关契约
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from .base import BaseContract
from .probe import ProbeResult


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


@dataclass(slots=True)
class DiagnosisEvidence(BaseContract):
    """诊断证据链"""
    
    step_name: str                          # 产生证据的步骤
    description: str                        # 证据描述
    probe_results: List[ProbeResult] = field(default_factory=list)
    config_snapshots: Dict[str, Any] = field(default_factory=dict)
    conclusion_hint: str = ""               # 指向的结论


@dataclass(slots=True)
class RootCause(BaseContract):
    """根因分析结果"""
    
    cause_id: str                           # 根因ID
    title: str                              # 根因标题
    description: str                        # 详细描述
    severity: Severity = Severity.WARNING
    confidence: float = 0.0                 # 置信度 0-1
    evidence_refs: List[str] = field(default_factory=list)  # 证据ID列表
    matched_rules: List[str] = field(default_factory=list)  # 匹配的规则


@dataclass(slots=True)
class Recommendation(BaseContract):
    """诊断建议"""
    
    action: str                             # 建议动作
    priority: int = 1                       # 优先级 1-5
    expected_outcome: str = ""              # 预期结果
    risk_level: Severity = Severity.INFO    # 操作风险等级
    commands: List[str] = field(default_factory=list)  # 可执行命令


@dataclass(slots=True)
class DiagnosisResult(BaseContract):
    """最终诊断结果"""
    
    # 基本信息
    diagnosis_type: str                     # quick_check / deep_dive / waterfall
    target_description: str                 # 诊断目标描述
    
    # 结论
    severity: Severity = Severity.INFO
    summary: str = ""                       # 一句话总结
    root_causes: List[RootCause] = field(default_factory=list)
    
    # 证据
    evidences: List[DiagnosisEvidence] = field(default_factory=list)
    
    # 建议
    recommendations: List[Recommendation] = field(default_factory=list)
    
    # 元信息
    overall_confidence: float = 0.0
    diagnosis_duration_ms: float = 0.0
    rule_version: str = "1.0.0"