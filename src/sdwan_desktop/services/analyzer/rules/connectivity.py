"""
互联网连通性规则 (INET-001 ~ INET-003)

遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
使用 @pure_function 装饰器标记评估函数
"""

import logging
from typing import Any, Dict, List

from sdwan_desktop.services.analyzer.rule_engine import Severity
from sdwan_desktop.tools.registry.decorator import pure_function

logger = logging.getLogger(__name__)


@pure_function
def _evaluate_inet_001(ctx: Any) -> bool:
    """INET-001: 国内网络不通

    国内目标全部不可达。
    """
    domestic_results = ctx.domestic_target_results
    if not domestic_results:
        return False
    return all(not r.success for r in domestic_results)


@pure_function
def _evaluate_inet_002(ctx: Any) -> bool:
    """INET-002: 国际网络不通

    国际目标全部不可达。
    """
    international_results = ctx.international_target_results
    if not international_results:
        return False
    return all(not r.success for r in international_results)


@pure_function
def _evaluate_inet_003(ctx: Any) -> bool:
    """INET-003: 国际链路丢包严重

    国际链路丢包率超过10%。
    """
    international_results = ctx.international_target_results
    if not international_results:
        return False

    # 计算国际目标的平均丢包率
    loss_rates = []
    for r in international_results:
        if r.metrics and r.metrics.loss_rate is not None:
            loss_rates.append(r.metrics.loss_rate)

    if not loss_rates:
        return False

    avg_loss_rate = sum(loss_rates) / len(loss_rates)
    return avg_loss_rate > 0.10


@pure_function
def _build_inet_001_message(ctx: Any) -> str:
    """构建INET-001诊断消息"""
    return "无法访问国内网站"


@pure_function
def _build_inet_002_message(ctx: Any) -> str:
    """构建INET-002诊断消息"""
    return "无法访问国际网站"


@pure_function
def _build_inet_003_message(ctx: Any) -> str:
    """构建INET-003诊断消息"""
    international_results = ctx.international_target_results
    loss_rates = []
    for r in international_results:
        if r.metrics and r.metrics.loss_rate is not None:
            loss_rates.append(r.metrics.loss_rate)
    avg_loss_rate = sum(loss_rates) / len(loss_rates) if loss_rates else 0.0
    return f"国际链路丢包率 {avg_loss_rate * 100:.1f}%"


# 互联网连通性规则定义
CONNECTIVITY_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "INET-001",
        "name": "国内网络不通",
        "severity": Severity.ERROR,
        "confidence": 0.90,
        "description": "无法访问国内网站",
        "suggestion": "检查网络连接、DNS设置或ISP服务状态",
        "evaluate_fn": _evaluate_inet_001,
        "message_fn": _build_inet_001_message,
    },
    {
        "rule_id": "INET-002",
        "name": "国际网络不通",
        "severity": Severity.WARNING,
        "confidence": 0.85,
        "description": "无法访问国际网站",
        "suggestion": "检查是否需要配置代理或VPN",
        "evaluate_fn": _evaluate_inet_002,
        "message_fn": _build_inet_002_message,
    },
    {
        "rule_id": "INET-003",
        "name": "国际链路丢包严重",
        "severity": Severity.WARNING,
        "confidence": 0.80,
        "description": "国际链路丢包率超过10%",
        "suggestion": "国际链路质量较差，建议联系ISP或使用专线",
        "evaluate_fn": _evaluate_inet_003,
        "message_fn": _build_inet_003_message,
    },
]
