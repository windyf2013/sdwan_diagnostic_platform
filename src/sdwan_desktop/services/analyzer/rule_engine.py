"""
规则引擎 - 一键体检规则评估引擎

遵循 SDWAN_SPEC.md §2.3 流程规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from sdwan_desktop.tools.registry.decorator import pure_function

logger = logging.getLogger(__name__)


class Severity(Enum):
    """规则严重级别"""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(slots=True)
class RuleResult:
    """单条规则评估结果"""

    rule_id: str
    """规则ID，如 GW-001"""

    name: str
    """规则名称"""

    triggered: bool
    """是否触发"""

    severity: Severity
    """严重级别"""

    confidence: float
    """置信度 (0-1)"""

    message: str = ""
    """诊断消息"""

    suggestion: str = ""
    """修复建议"""

    details: Dict[str, Any] = field(default_factory=dict)
    """额外详情"""


@dataclass(slots=True)
class RuleEngineResult:
    """规则引擎评估结果聚合"""

    results: List[RuleResult] = field(default_factory=list)
    """所有规则评估结果"""

    total_rules: int = 0
    """规则总数"""

    triggered_count: int = 0
    """触发规则数"""

    critical_count: int = 0
    """严重级别触发数"""

    error_count: int = 0
    """错误级别触发数"""

    warning_count: int = 0
    """警告级别触发数"""

    info_count: int = 0
    """信息级别触发数"""

    @property
    def has_issues(self) -> bool:
        """是否存在问题"""
        return self.triggered_count > 0

    @property
    def has_critical_issues(self) -> bool:
        """是否存在严重问题"""
        return self.critical_count > 0

    @property
    def score(self) -> int:
        """健康评分 (0-100)

        根据触发规则的严重级别计算扣分：
        - CRITICAL: 扣30分/条
        - ERROR: 扣20分/条
        - WARNING: 扣10分/条
        - INFO: 扣5分/条
        """
        deductions = (
            self.critical_count * 30
            + self.error_count * 20
            + self.warning_count * 10
            + self.info_count * 5
        )
        return max(0, 100 - deductions)


@dataclass(slots=True)
class RuleDef:
    """规则定义 - 纯数据容器"""

    rule_id: str
    """规则ID"""

    name: str
    """规则名称"""

    severity: Severity
    """严重级别"""

    confidence: float
    """置信度 (0-1)"""

    description: str = ""
    """规则描述"""

    suggestion: str = ""
    """修复建议"""


class RuleEngine:
    """规则引擎

    管理所有诊断规则，对 QuickCheckContext 进行规则评估。
    规则使用 @pure_function 装饰器标记，确保无副作用。
    """

    def __init__(self):
        """初始化规则引擎"""
        self._rules: List[Dict[str, Any]] = []
        self._initialized = False

    def register_rule(
        self,
        rule_id: str,
        name: str,
        severity: Severity,
        confidence: float,
        evaluate_fn: Callable[[Any], bool],
        description: str = "",
        suggestion: str = "",
        message_fn: Optional[Callable[[Any], str]] = None,
    ) -> None:
        """注册一条规则

        Args:
            rule_id: 规则ID
            name: 规则名称
            severity: 严重级别
            confidence: 置信度
            evaluate_fn: 评估函数，接收 QuickCheckContext 返回 bool
            description: 规则描述
            suggestion: 修复建议
            message_fn: 消息构建函数，接收 QuickCheckContext 返回 str
        """
        self._rules.append({
            "rule_id": rule_id,
            "name": name,
            "severity": severity,
            "confidence": confidence,
            "description": description,
            "suggestion": suggestion,
            "evaluate_fn": evaluate_fn,
            "message_fn": message_fn,
        })

    def register_rules(self, rules: List[Dict[str, Any]]) -> None:
        """批量注册规则

        Args:
            rules: 规则定义列表，每项包含 rule_id, name, severity,
                   confidence, evaluate_fn, description, suggestion
        """
        for rule in rules:
            self.register_rule(
                rule_id=rule["rule_id"],
                name=rule["name"],
                severity=rule["severity"],
                confidence=rule["confidence"],
                evaluate_fn=rule["evaluate_fn"],
                description=rule.get("description", ""),
                suggestion=rule.get("suggestion", ""),
            )

    @pure_function
    def evaluate(self, ctx: Any) -> RuleEngineResult:
        """评估所有规则

        Args:
            ctx: QuickCheckContext 实例

        Returns:
            RuleEngineResult: 规则评估结果聚合
        """
        result = RuleEngineResult(total_rules=len(self._rules))

        for rule_def in self._rules:
            try:
                triggered = rule_def["evaluate_fn"](ctx)

                rule_result = RuleResult(
                    rule_id=rule_def["rule_id"],
                    name=rule_def["name"],
                    triggered=triggered,
                    severity=rule_def["severity"],
                    confidence=rule_def["confidence"],
                    message=self._build_message(rule_def, ctx),
                    suggestion=rule_def["suggestion"],
                )
                result.results.append(rule_result)

                if triggered:
                    result.triggered_count += 1
                    if rule_def["severity"] == Severity.CRITICAL:
                        result.critical_count += 1
                    elif rule_def["severity"] == Severity.ERROR:
                        result.error_count += 1
                    elif rule_def["severity"] == Severity.WARNING:
                        result.warning_count += 1
                    elif rule_def["severity"] == Severity.INFO:
                        result.info_count += 1

            except Exception as e:
                logger.error(
                    f"规则评估异常 [{rule_def['rule_id']}]: {e}",
                )
                result.results.append(RuleResult(
                    rule_id=rule_def["rule_id"],
                    name=rule_def["name"],
                    triggered=True,
                    severity=Severity.WARNING,
                    confidence=0.5,
                    message=f"规则评估异常: {e}",
                    suggestion="请联系开发人员检查规则配置",
                ))
                result.triggered_count += 1
                result.warning_count += 1

        return result

    def _build_message(self, rule_def: Dict[str, Any], ctx: Any) -> str:
        """构建诊断消息

        优先使用 message_fn 构建消息，否则使用 description。

        Args:
            rule_def: 规则定义
            ctx: QuickCheckContext

        Returns:
            str: 诊断消息
        """
        message_fn = rule_def.get("message_fn")
        if message_fn is not None:
            try:
                return message_fn(ctx)
            except Exception as e:
                logger.warning(
                    f"消息构建异常 [{rule_def['rule_id']}]: {e}",
                )
        return rule_def.get("description", rule_def["name"])

    @property
    def rules_count(self) -> int:
        """已注册规则数"""
        return len(self._rules)

    def clear_rules(self) -> None:
        """清除所有规则"""
        self._rules.clear()
