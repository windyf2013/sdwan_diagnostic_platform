"""
延迟规则

检查网络延迟是否在正常范围内
"""

import logging
from typing import Any, Dict

from sdwan_desktop.core.types.context import FlowContext
from ..rule_engine import BaseRule, RuleResult, RuleSeverity

logger = logging.getLogger(__name__)


class LatencyRule(BaseRule):
    """延迟检查规则
    
    检查端到端延迟是否在正常范围内
    """
    
    def __init__(self):
        """初始化延迟规则"""
        super().__init__(
            rule_id="LAT-001",
            rule_name="网络延迟检查",
            severity=RuleSeverity.WARNING
        )
        self.good_threshold_ms = 50
        """良好延迟阈值（毫秒）"""
        self.warning_threshold_ms = 150
        """警告延迟阈值（毫秒）"""
    
    async def evaluate(self, data: Dict[str, Any], ctx: FlowContext) -> RuleResult:
        """评估网络延迟
        
        Args:
            data: 诊断数据，需包含:
                - ping_result: dict, Ping测试结果
                - target: str, 目标地址（可选）
            ctx: 流程上下文
            
        Returns:
            规则执行结果
        """
        ping_data = data.get("ping_result", data)
        target = data.get("target", "目标主机")
        
        if not ping_data:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                severity=RuleSeverity.ERROR,
                message="缺少Ping数据，无法评估延迟",
                suggestions=["请确保已执行连通性测试"],
            )
        
        # 检查Ping是否成功
        ping_success = ping_data.get("success", False)
        if not ping_success:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                severity=RuleSeverity.ERROR,
                message=f"无法测量到 {target} 的延迟",
                details=ping_data,
                suggestions=["检查目标主机是否在线", "检查网络连通性"],
            )
        
        # 获取RTT指标
        rtt_avg = ping_data.get("rtt_avg", 0)
        rtt_min = ping_data.get("rtt_min", 0)
        rtt_max = ping_data.get("rtt_max", 0)
        rtt_stddev = ping_data.get("rtt_stddev", 0)
        
        # 评估延迟级别
        if rtt_avg <= self.good_threshold_ms:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                severity=RuleSeverity.INFO,
                message=f"到 {target} 的延迟正常: 平均{rtt_avg:.1f}ms",
                details={
                    "target": target,
                    "rtt_avg": rtt_avg,
                    "rtt_min": rtt_min,
                    "rtt_max": rtt_max,
                    "rtt_stddev": rtt_stddev,
                },
                confidence=0.95,
            )
        
        elif rtt_avg <= self.warning_threshold_ms:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                severity=RuleSeverity.INFO,
                message=f"到 {target} 的延迟略高: 平均{rtt_avg:.1f}ms",
                details={
                    "target": target,
                    "rtt_avg": rtt_avg,
                    "rtt_min": rtt_min,
                    "rtt_max": rtt_max,
                    "rtt_stddev": rtt_stddev,
                },
                suggestions=[
                    "检查是否存在网络拥塞",
                    "考虑优化路由路径",
                ],
                confidence=0.85,
            )
        
        else:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                severity=RuleSeverity.WARNING,
                message=f"到 {target} 的延迟过高: 平均{rtt_avg:.1f}ms (阈值: {self.warning_threshold_ms}ms)",
                details={
                    "target": target,
                    "rtt_avg": rtt_avg,
                    "rtt_min": rtt_min,
                    "rtt_max": rtt_max,
                    "rtt_stddev": rtt_stddev,
                },
                suggestions=[
                    "检查网络带宽使用情况",
                    "检查是否存在路由环路",
                    "考虑使用QoS优化延迟敏感流量",
                    "联系ISP检查网络质量",
                ],
                confidence=0.9,
            )
