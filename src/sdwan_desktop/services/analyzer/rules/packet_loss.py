"""
丢包率规则

检查网络丢包率是否在正常范围内
"""

import logging
from typing import Any, Dict

from sdwan_desktop.core.types.context import FlowContext
from ..rule_engine import BaseRule, RuleResult, RuleSeverity

logger = logging.getLogger(__name__)


class PacketLossRule(BaseRule):
    """丢包率检查规则
    
    检查网络丢包率是否在正常范围内
    """
    
    def __init__(self):
        """初始化丢包率规则"""
        super().__init__(
            rule_id="LOS-001",
            rule_name="丢包率检查",
            severity=RuleSeverity.ERROR
        )
        self.good_threshold = 0.01
        """良好丢包率阈值 (1%)"""
        self.warning_threshold = 0.05
        """警告丢包率阈值 (5%)"""
    
    async def evaluate(self, data: Dict[str, Any], ctx: FlowContext) -> RuleResult:
        """评估丢包率
        
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
                message="缺少Ping数据，无法评估丢包率",
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
                message=f"无法测量到 {target} 的丢包率",
                details=ping_data,
                suggestions=["检查目标主机是否在线", "检查网络连通性"],
            )
        
        # 获取丢包率
        loss_rate = ping_data.get("loss_rate", 0)
        packets_sent = ping_data.get("packets_sent", 0)
        packets_received = ping_data.get("packets_received", 0)
        
        # 评估丢包级别
        if loss_rate == 0:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                severity=RuleSeverity.INFO,
                message=f"到 {target} 的丢包率为0%，网络质量良好",
                details={
                    "target": target,
                    "loss_rate": loss_rate,
                    "packets_sent": packets_sent,
                    "packets_received": packets_received,
                },
                confidence=0.95,
            )
        
        elif loss_rate <= self.good_threshold:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                severity=RuleSeverity.INFO,
                message=f"到 {target} 的丢包率在可接受范围内: {loss_rate:.1%}",
                details={
                    "target": target,
                    "loss_rate": loss_rate,
                    "packets_sent": packets_sent,
                    "packets_received": packets_received,
                },
                confidence=0.9,
            )
        
        elif loss_rate <= self.warning_threshold:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                severity=RuleSeverity.WARNING,
                message=f"到 {target} 存在轻度丢包: {loss_rate:.1%} (阈值: {self.warning_threshold:.1%})",
                details={
                    "target": target,
                    "loss_rate": loss_rate,
                    "packets_sent": packets_sent,
                    "packets_received": packets_received,
                },
                suggestions=[
                    "检查网络链路质量",
                    "检查是否存在网络拥塞",
                    "检查网线/无线信号质量",
                ],
                confidence=0.85,
            )
        
        else:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                severity=RuleSeverity.ERROR,
                message=f"到 {target} 存在严重丢包: {loss_rate:.1%} (阈值: {self.warning_threshold:.1%})",
                details={
                    "target": target,
                    "loss_rate": loss_rate,
                    "packets_sent": packets_sent,
                    "packets_received": packets_received,
                },
                suggestions=[
                    "立即检查网络物理连接",
                    "检查交换机/路由器端口状态",
                    "检查是否存在广播风暴",
                    "联系网络管理员",
                ],
                confidence=0.95,
            )
