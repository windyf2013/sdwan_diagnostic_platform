"""
系统配置规则 (ADAPTER-001 ~ ADAPTER-002, IP-001 ~ IP-002,
              ROUTE-001 ~ ROUTE-002, PROXY-001 ~ PROXY-002,
              FW-001, IPV6-001)

遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
使用 @pure_function 装饰器标记评估函数
"""

import logging
from typing import Any, Dict, List

from sdwan_desktop.services.analyzer.rule_engine import Severity
from sdwan_desktop.tools.registry.decorator import pure_function

logger = logging.getLogger(__name__)


# ==================== 网卡规则 ====================


@pure_function
def _evaluate_adapter_001(ctx: Any) -> bool:
    """ADAPTER-001: 网卡未连接"""
    adapter = ctx.primary_adapter
    if adapter is None:
        return False
    return not adapter.is_connected


@pure_function
def _evaluate_adapter_002(ctx: Any) -> bool:
    """ADAPTER-002: 网卡速度异常"""
    adapter = ctx.primary_adapter
    if adapter is None:
        return False
    speed = adapter.speed_mbps
    if speed is None:
        return False
    return speed < 100


@pure_function
def _build_adapter_001_message(ctx: Any) -> str:
    """构建ADAPTER-001诊断消息"""
    return "主网卡未连接"


@pure_function
def _build_adapter_002_message(ctx: Any) -> str:
    """构建ADAPTER-002诊断消息"""
    speed = 0
    if ctx.primary_adapter and ctx.primary_adapter.speed_mbps is not None:
        speed = ctx.primary_adapter.speed_mbps
    return f"网卡协商速率过低 ({speed}Mbps)"


# ==================== IP配置规则 ====================


@pure_function
def _evaluate_ip_001(ctx: Any) -> bool:
    """IP-001: APIPA地址"""
    ip_config = ctx.ip_config
    if ip_config is None or not ip_config.ip_address:
        return False
    return ip_config.ip_address.startswith("169.254")


@pure_function
def _evaluate_ip_002(ctx: Any) -> bool:
    """IP-002: IP地址冲突

    通过ARP表检测是否有重复IP。
    """
    arp_table = ctx.arp_table
    if not arp_table:
        return False

    # 检查ARP表中是否有重复IP
    ip_counts: Dict[str, int] = {}
    for entry in arp_table:
        ip = getattr(entry, "ip_address", None) or getattr(entry, "ip", None)
        if ip:
            ip_counts[ip] = ip_counts.get(ip, 0) + 1

    return any(count > 1 for count in ip_counts.values())


@pure_function
def _build_ip_001_message(ctx: Any) -> str:
    """构建IP-001诊断消息"""
    return "获取到自动配置IP地址(169.254.x.x)，DHCP可能失败"


@pure_function
def _build_ip_002_message(ctx: Any) -> str:
    """构建IP-002诊断消息"""
    return "检测到IP地址冲突"


# ==================== 路由规则 ====================


@pure_function
def _evaluate_route_001(ctx: Any) -> bool:
    """ROUTE-001: 多条默认路由"""
    return len(ctx.default_routes) > 1


@pure_function
def _evaluate_route_002(ctx: Any) -> bool:
    """ROUTE-002: 默认路由metric过高"""
    default_routes = ctx.default_routes
    if not default_routes:
        return False
    # 取第一条默认路由的metric
    metric = default_routes[0].metric
    if metric is None:
        return False
    return metric > 100


@pure_function
def _build_route_001_message(ctx: Any) -> str:
    """构建ROUTE-001诊断消息"""
    return f"存在 {len(ctx.default_routes)} 条默认路由"


@pure_function
def _build_route_002_message(ctx: Any) -> str:
    """构建ROUTE-002诊断消息"""
    metric = 0
    default_routes = ctx.default_routes
    if default_routes and default_routes[0].metric is not None:
        metric = default_routes[0].metric
    return f"默认路由Metric值为 {metric}"


# ==================== 代理规则 ====================


@pure_function
def _evaluate_proxy_001(ctx: Any) -> bool:
    """PROXY-001: 系统代理已启用"""
    proxy = ctx.proxy_config
    if proxy is None:
        return False
    return proxy.enabled


@pure_function
def _evaluate_proxy_002(ctx: Any) -> bool:
    """PROXY-002: 代理配置异常

    代理已启用但配置不完整或格式错误。
    检查项:
    1. 代理服务器地址是否为空
    2. 代理地址格式是否有效(应包含协议和端口)
    """
    proxy = ctx.proxy_config
    if proxy is None or not proxy.enabled:
        return False
    
    # 检查代理服务器地址是否为空
    if not proxy.server:
        return True
    
    # 检查代理地址格式(简单验证:应包含 :// 或 :port)
    server = proxy.server.strip()
    has_protocol = "://" in server
    has_port = ":" in server.split("//")[-1]  # 排除协议部分的冒号
    
    # 如果既没有协议也没有端口,可能是配置不完整
    if not has_protocol and not has_port:
        return True
    
    return False


@pure_function
def _build_proxy_001_message(ctx: Any) -> str:
    """构建PROXY-001诊断消息"""
    server = "未知"
    if ctx.proxy_config and ctx.proxy_config.server:
        server = ctx.proxy_config.server
    return f"系统代理已启用: {server}"


@pure_function
def _build_proxy_002_message(ctx: Any) -> str:
    """构建PROXY-002诊断消息"""
    proxy = ctx.proxy_config
    if proxy is None:
        return "代理配置异常"
    
    server = proxy.server or "未配置"
    
    # 根据具体问题生成不同的消息
    if not proxy.server:
        return "代理已启用但服务器地址为空"
    
    # 检查格式问题
    server_stripped = server.strip()
    has_protocol = "://" in server_stripped
    has_port = ":" in server_stripped.split("//")[-1]
    
    if not has_protocol and not has_port:
        return f"代理地址格式可能不完整: {server} (建议添加协议和端口)"
    
    return f"代理配置可能存在连接问题: {server}"


# ==================== 防火墙规则 ====================


@pure_function
def _evaluate_fw_001(ctx: Any) -> bool:
    """FW-001: 防火墙阻止ICMP"""
    firewall = ctx.firewall_status
    if firewall is None:
        return False
    return getattr(firewall, "icmp_blocked", False)


@pure_function
def _build_fw_001_message(ctx: Any) -> str:
    """构建FW-001诊断消息"""
    return "Windows防火墙可能阻止了ICMP回显请求"


# ==================== IPv6规则 ====================


@pure_function
def _evaluate_ipv6_001(ctx: Any) -> bool:
    """IPV6-001: IPv6优先导致延迟"""
    ipv6 = ctx.ipv6
    if ipv6 is None:
        return False
    return getattr(ipv6, "enabled", False) and getattr(ipv6, "is_preferred", False)


@pure_function
def _build_ipv6_001_message(ctx: Any) -> str:
    """构建IPV6-001诊断消息"""
    return "IPv6已启用且优先级高于IPv4"


# ==================== 规则汇总 ====================

SYSTEM_RULES: List[Dict[str, Any]] = [
    # 网卡规则
    {
        "rule_id": "ADAPTER-001",
        "name": "网卡未连接",
        "severity": Severity.CRITICAL,
        "confidence": 0.95,
        "description": "主网卡未连接",
        "suggestion": "请检查网线连接或WiFi是否已连接",
        "evaluate_fn": _evaluate_adapter_001,
        "message_fn": _build_adapter_001_message,
    },
    {
        "rule_id": "ADAPTER-002",
        "name": "网卡速度异常",
        "severity": Severity.WARNING,
        "confidence": 0.90,
        "description": "网卡协商速率低于100Mbps",
        "suggestion": "建议检查网线质量或更换千兆网卡",
        "evaluate_fn": _evaluate_adapter_002,
        "message_fn": _build_adapter_002_message,
    },
    # IP配置规则
    {
        "rule_id": "IP-001",
        "name": "APIPA地址",
        "severity": Severity.CRITICAL,
        "confidence": 0.95,
        "description": "获取到自动配置IP地址(169.254.x.x)，DHCP可能失败",
        "suggestion": "检查DHCP服务器状态或手动配置静态IP",
        "evaluate_fn": _evaluate_ip_001,
        "message_fn": _build_ip_001_message,
    },
    {
        "rule_id": "IP-002",
        "name": "IP地址冲突",
        "severity": Severity.ERROR,
        "confidence": 0.85,
        "description": "检测到IP地址冲突",
        "suggestion": "检查网络中是否有重复IP地址",
        "evaluate_fn": _evaluate_ip_002,
        "message_fn": _build_ip_002_message,
    },
    # 路由规则
    {
        "rule_id": "ROUTE-001",
        "name": "多条默认路由",
        "severity": Severity.WARNING,
        "confidence": 0.85,
        "description": "存在多条默认路由",
        "suggestion": "检查是否同时连接多个网络，可能导致路由冲突",
        "evaluate_fn": _evaluate_route_001,
        "message_fn": _build_route_001_message,
    },
    {
        "rule_id": "ROUTE-002",
        "name": "默认路由metric过高",
        "severity": Severity.INFO,
        "confidence": 0.75,
        "description": "默认路由Metric值过高",
        "suggestion": "可适当降低Metric值以提高优先级",
        "evaluate_fn": _evaluate_route_002,
        "message_fn": _build_route_002_message,
    },
    # 代理规则
    {
        "rule_id": "PROXY-001",
        "name": "系统代理已启用",
        "severity": Severity.INFO,
        "confidence": 0.95,
        "description": "系统代理已启用",
        "suggestion": "如非必要，建议关闭代理以避免流量被错误转发",
        "evaluate_fn": _evaluate_proxy_001,
        "message_fn": _build_proxy_001_message,
    },
    {
        "rule_id": "PROXY-002",
        "name": "代理配置异常",
        "severity": Severity.WARNING,
        "confidence": 0.85,
        "description": "代理已启用但配置不完整或格式错误",
        "suggestion": "检查代理服务器地址格式(应包含协议和端口),或临时关闭代理",
        "evaluate_fn": _evaluate_proxy_002,
        "message_fn": _build_proxy_002_message,
    },
    # 防火墙规则
    {
        "rule_id": "FW-001",
        "name": "防火墙阻止ICMP",
        "severity": Severity.INFO,
        "confidence": 0.80,
        "description": "Windows防火墙可能阻止了ICMP回显请求",
        "suggestion": "如需使用Ping功能，请允许'文件和打印机共享(回显请求-ICMPv4-In)'规则",
        "evaluate_fn": _evaluate_fw_001,
        "message_fn": _build_fw_001_message,
    },
    # IPv6规则
    {
        "rule_id": "IPV6-001",
        "name": "IPv6优先导致延迟",
        "severity": Severity.INFO,
        "confidence": 0.75,
        "description": "IPv6已启用且优先级高于IPv4",
        "suggestion": "如果不需要IPv6，可在网卡属性中禁用",
        "evaluate_fn": _evaluate_ipv6_001,
        "message_fn": _build_ipv6_001_message,
    },
]
