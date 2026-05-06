"""
DNS解析规则 (DNS-001 ~ DNS-002, SPLIT-001)

遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
使用 @pure_function 装饰器标记评估函数
"""

import logging
from typing import Any, Dict, List

from sdwan_desktop.services.analyzer.rule_engine import Severity
from sdwan_desktop.tools.registry.decorator import pure_function

logger = logging.getLogger(__name__)


@pure_function
def _evaluate_dns_001(ctx: Any) -> bool:
    """DNS-001: DNS服务器无响应

    所有DNS服务器均无响应。
    """
    domestic_results = ctx.domestic_dns_results
    international_results = ctx.international_dns_results

    all_results = list(domestic_results) + list(international_results)
    if not all_results:
        return False

    # 所有DNS查询都失败
    return all(not r.success for r in all_results)


@pure_function
def _evaluate_dns_002(ctx: Any) -> bool:
    """DNS-002: DNS响应慢

    DNS平均响应时间超过500ms。
    """
    domestic_results = ctx.domestic_dns_results
    international_results = ctx.international_dns_results

    all_results = list(domestic_results) + list(international_results)
    if not all_results:
        return False

    # 计算平均响应时间
    rtt_values = []
    for r in all_results:
        if r.success and r.metrics and r.metrics.rtt_avg is not None:
            rtt_values.append(r.metrics.rtt_avg)

    if not rtt_values:
        return False

    avg_rtt = sum(rtt_values) / len(rtt_values)
    return avg_rtt > 500


@pure_function
def _evaluate_split_001(ctx: Any) -> bool:
    """SPLIT-001: DNS分流异常

    DNS解析结果与预期不符，可能存在DNS劫持或配置问题。
    """
    return ctx.has_dns_split_anomaly


@pure_function
def _build_dns_001_message(ctx: Any) -> str:
    """构建DNS-001诊断消息"""
    return "所有DNS服务器均无响应"


@pure_function
def _build_dns_002_message(ctx: Any) -> str:
    """构建DNS-002诊断消息"""
    domestic_results = ctx.domestic_dns_results
    international_results = ctx.international_dns_results
    all_results = list(domestic_results) + list(international_results)

    rtt_values = []
    for r in all_results:
        if r.success and r.metrics and r.metrics.rtt_avg is not None:
            rtt_values.append(r.metrics.rtt_avg)

    avg_rtt = sum(rtt_values) / len(rtt_values) if rtt_values else 0.0
    return f"DNS平均响应时间 {avg_rtt:.0f}ms"


@pure_function
def _build_split_001_message(ctx: Any) -> str:
    """构建SPLIT-001诊断消息"""
    split_domains = ctx.dns_split.split_domains
    if split_domains:
        domains_str = ", ".join(split_domains[:5])
        if len(split_domains) > 5:
            domains_str += f" 等{len(split_domains)}个域名"
        return f"DNS分流异常域名: {domains_str}"
    return "DNS解析结果与预期不符，可能存在DNS劫持或配置问题"


# DNS规则定义
DNS_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "DNS-001",
        "name": "DNS服务器无响应",
        "severity": Severity.ERROR,
        "confidence": 0.90,
        "description": "所有DNS服务器均无响应",
        "suggestion": "检查DNS服务器配置或使用公共DNS如114.114.114.114",
        "evaluate_fn": _evaluate_dns_001,
        "message_fn": _build_dns_001_message,
    },
    {
        "rule_id": "DNS-002",
        "name": "DNS响应慢",
        "severity": Severity.WARNING,
        "confidence": 0.80,
        "description": "DNS平均响应时间超过500ms",
        "suggestion": "建议更换响应更快的DNS服务器",
        "evaluate_fn": _evaluate_dns_002,
        "message_fn": _build_dns_002_message,
    },
    {
        "rule_id": "SPLIT-001",
        "name": "DNS分流异常",
        "severity": Severity.WARNING,
        "confidence": 0.70,
        "description": "DNS解析结果与预期不符，可能存在DNS劫持或配置问题",
        "suggestion": "检查DNS设置，建议使用DoH/DoT加密DNS",
        "evaluate_fn": _evaluate_split_001,
        "message_fn": _build_split_001_message,
    },
]
