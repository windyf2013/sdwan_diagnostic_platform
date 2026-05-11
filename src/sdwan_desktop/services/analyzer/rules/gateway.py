"""
网关连通性规则 (GW-001 ~ GW-003)

遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
使用 @pure_function 装饰器标记评估函数
"""

import logging
from typing import Any, Dict, List

from sdwan_desktop.services.analyzer.rule_engine import Severity
from sdwan_desktop.tools.registry.decorator import pure_function

logger = logging.getLogger(__name__)


@pure_function
def _evaluate_gw_001(ctx: Any) -> bool:
    """GW-001: 网关不可达

    无法Ping通默认网关。
    """
    gateway_ping = ctx.gateway_ping
    if gateway_ping is None:
        return False
    return not gateway_ping.success


@pure_function
def _evaluate_gw_002(ctx: Any) -> bool:
    """GW-002: 网关延迟过高

    网关平均延迟超过100ms。
    """
    gateway_ping = ctx.gateway_ping
    if gateway_ping is None or gateway_ping.metrics is None:
        return False
    rtt_avg = gateway_ping.metrics.rtt_avg
    if rtt_avg is None:
        return False
    return rtt_avg > 100


@pure_function
def _evaluate_gw_003(ctx: Any) -> bool:
    """GW-003: 网关丢包

    网关丢包率超过5%。
    """
    gateway_ping = ctx.gateway_ping
    if gateway_ping is None or gateway_ping.metrics is None:
        return False
    loss_rate = gateway_ping.metrics.loss_rate
    if loss_rate is None:
        return False
    return loss_rate > 0.05


@pure_function
def _build_gw_001_message(ctx: Any) -> str:
    """构建GW-001诊断消息"""
    gateway_ip = "未知"
    if ctx.ip_config and ctx.ip_config.default_gateway:
        gateway_ip = ctx.ip_config.default_gateway
    return f"无法Ping通网关 {gateway_ip}"


@pure_function
def _build_gw_002_message(ctx: Any) -> str:
    """构建GW-002诊断消息"""
    rtt_avg = 0.0
    if ctx.gateway_ping and ctx.gateway_ping.metrics:
        rtt_avg = ctx.gateway_ping.metrics.rtt_avg or 0.0
    return f"网关平均延迟 {rtt_avg:.1f}ms"


@pure_function
def _build_gw_003_message(ctx: Any) -> str:
    """构建GW-003诊断消息"""
    loss_rate = 0.0
    if ctx.gateway_ping and ctx.gateway_ping.metrics:
        loss_rate = ctx.gateway_ping.metrics.loss_rate or 0.0
    return f"网关丢包率 {loss_rate * 100:.1f}%"


# 网关规则定义
GATEWAY_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "GW-001",
        "name": "网关不可达",
        "severity": Severity.CRITICAL,
        "confidence": 0.95,
        "description": "无法Ping通默认网关",
        "suggestion": "检查网关设备状态、防火墙规则或ARP绑定",
        "evaluate_fn": _evaluate_gw_001,
        "message_fn": _build_gw_001_message,
    },
    {
        "rule_id": "GW-002",
        "name": "网关延迟过高",
        "severity": Severity.WARNING,
        "confidence": 0.85,
        "description": "网关平均延迟超过100ms",
        "suggestion": "检查网络负载或更换网关设备",
        "evaluate_fn": _evaluate_gw_002,
        "message_fn": _build_gw_002_message,
    },
    {
        "rule_id": "GW-003",
        "name": "网关丢包",
        "severity": Severity.WARNING,
        "confidence": 0.80,
        "description": "网关丢包率超过5%",
        "suggestion": "检查物理链路质量或是否存在环路",
        "evaluate_fn": _evaluate_gw_003,
        "message_fn": _build_gw_003_message,
    },
]
