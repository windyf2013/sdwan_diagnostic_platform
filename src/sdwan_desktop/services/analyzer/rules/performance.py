"""
性能诊断规则 - 基于 Waterfall 数据的纯函数规则

遵循 SDWAN_SPEC.md §2.2.3 函数分类标准 (pure_function)
"""

from typing import List, Dict, Any

from sdwan_desktop.core.types.waterfall import WaterfallResult, ResourceTiming
from sdwan_desktop.tools.registry.decorator import pure_function


# 默认阈值配置
THRESHOLDS = {
    "page_load_time": 3000,      # PERF-001: >3s
    "dns_time": 200,             # PERF-002: >200ms
    "connect_time": 300,         # PERF-003: >300ms
    "ssl_time": 500,             # PERF-004: >500ms
    "wait_time": 600,            # PERF-005: TTFB >600ms
    "download_time": 2000,       # PERF-006: >2s
}


@pure_function
def check_page_load_time(waterfall: WaterfallResult) -> List[Dict[str, Any]]:
    """PERF-001: 页面加载时间过长 (>3s)"""
    issues = []
    if waterfall.page_load_time > THRESHOLDS["page_load_time"]:
        issues.append({
            "rule_id": "PERF-001",
            "severity": "warning",
            "message": f"页面总加载时间过长: {waterfall.page_load_time:.0f}ms",
            "value": waterfall.page_load_time,
            "threshold": THRESHOLDS["page_load_time"]
        })
    return issues


@pure_function
def check_dns_performance(waterfall: WaterfallResult) -> List[Dict[str, Any]]:
    """PERF-002: DNS解析慢 (>200ms)"""
    issues = []
    for r in waterfall.resources:
        if r.dns_time > THRESHOLDS["dns_time"]:
            issues.append({
                "rule_id": "PERF-002",
                "severity": "info",
                "message": f"DNS解析耗时过长: {r.url}",
                "url": r.url,
                "value": r.dns_time,
                "threshold": THRESHOLDS["dns_time"]
            })
    return issues


@pure_function
def check_tcp_connect_performance(waterfall: WaterfallResult) -> List[Dict[str, Any]]:
    """PERF-003: TCP握手慢 (>300ms)"""
    issues = []
    for r in waterfall.resources:
        if r.connect_time > THRESHOLDS["connect_time"]:
            issues.append({
                "rule_id": "PERF-003",
                "severity": "info",
                "message": f"TCP连接建立耗时过长: {r.url}",
                "url": r.url,
                "value": r.connect_time,
                "threshold": THRESHOLDS["connect_time"]
            })
    return issues


@pure_function
def check_ssl_handshake_performance(waterfall: WaterfallResult) -> List[Dict[str, Any]]:
    """PERF-004: SSL握手慢 (>500ms)"""
    issues = []
    for r in waterfall.resources:
        if r.ssl_time > THRESHOLDS["ssl_time"]:
            issues.append({
                "rule_id": "PERF-004",
                "severity": "info",
                "message": f"SSL握手耗时过长: {r.url}",
                "url": r.url,
                "value": r.ssl_time,
                "threshold": THRESHOLDS["ssl_time"]
            })
    return issues


@pure_function
def check_ttfb_performance(waterfall: WaterfallResult) -> List[Dict[str, Any]]:
    """PERF-005: TTFB过长 (>600ms)"""
    issues = []
    for r in waterfall.resources:
        if r.wait_time > THRESHOLDS["wait_time"]:
            issues.append({
                "rule_id": "PERF-005",
                "severity": "warning",
                "message": f"服务器响应等待时间(TTFB)过长: {r.url}",
                "url": r.url,
                "value": r.wait_time,
                "threshold": THRESHOLDS["wait_time"]
            })
    return issues


@pure_function
def check_download_performance(waterfall: WaterfallResult) -> List[Dict[str, Any]]:
    """PERF-006: 资源下载慢 (>2s)"""
    issues = []
    for r in waterfall.resources:
        if r.download_time > THRESHOLDS["download_time"]:
            issues.append({
                "rule_id": "PERF-006",
                "severity": "warning",
                "message": f"资源下载耗时过长: {r.url}",
                "url": r.url,
                "value": r.download_time,
                "threshold": THRESHOLDS["download_time"]
            })
    return issues


@pure_function
def check_render_blocking(waterfall: WaterfallResult) -> List[Dict[str, Any]]:
    """PERF-007: 阻塞渲染资源"""
    issues = []
    blocking_resources = [r for r in waterfall.resources if r.is_render_blocking]
    if blocking_resources:
        issues.append({
            "rule_id": "PERF-007",
            "severity": "info",
            "message": f"发现 {len(blocking_resources)} 个阻塞渲染的资源",
            "urls": [r.url for r in blocking_resources],
            "count": len(blocking_resources)
        })
    return issues
