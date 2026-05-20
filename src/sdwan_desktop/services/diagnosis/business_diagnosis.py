"""业务域名:端口 诊断编排：探测执行（根由 ``BusinessPathAnalyzer`` / ``RootCauseEngine`` 单独归纳）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Awaitable, Dict, List, Optional, Sequence

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.services.probe.business_host_probe import (
    DEFAULT_MAX_ADDRS_PER_DOMAIN,
    DEFAULT_TCP_COUNT,
    DEFAULT_TCP_TIMEOUT,
    DEFAULT_TRACEROUTE_MAX_HOPS,
    DEFAULT_TRACEROUTE_PROTOCOL,
    DEFAULT_TRACEROUTE_TIMEOUT,
    BizDomainPortSpec,
    run_business_domain_port_probes,
)
from sdwan_desktop.tools.registry.base import ToolDispatcher

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BusinessDiagnosisOutcome:
    """业务主机探测一次执行的聚合结果（不含根因，避免与 ``RootCauseEngine`` 重复）。"""

    status: str
    """``ok`` 或 ``partial``（与探测聚合错误一致）。"""

    business_probes: List[Dict[str, Any]]
    aggregate_error: Optional[str]

    def to_json_payload(self) -> Dict[str, Any]:
        """可 JSON 序列化的摘要结构（仅探测数据）。"""
        return {
            "status": self.status,
            "aggregate_error": self.aggregate_error,
            "business_probes": self.business_probes,
        }


async def orchestrate_business_domain_port_diagnosis(
    ctx: FlowContext,
    targets: Sequence[BizDomainPortSpec],
    dns_server: Optional[str],
    dispatcher: Optional[ToolDispatcher] = None,
    *,
    max_addrs_per_domain: int = DEFAULT_MAX_ADDRS_PER_DOMAIN,
    tcp_count: int = DEFAULT_TCP_COUNT,
    tcp_timeout: int = DEFAULT_TCP_TIMEOUT,
    compare_system_dns: bool = False,
    enable_traceroute: bool = True,
    traceroute_max_hops: int = DEFAULT_TRACEROUTE_MAX_HOPS,
    traceroute_timeout: int = DEFAULT_TRACEROUTE_TIMEOUT,
    traceroute_protocol: str = DEFAULT_TRACEROUTE_PROTOCOL,
    on_biz_ips_ready: Optional[Callable[[List[str]], Awaitable[None]]] = None,
    on_tcp_probe_done: Optional[Callable[[List[str]], Awaitable[None]]] = None,
) -> BusinessDiagnosisOutcome:
    """执行 DNS(A)+TCP+可选 traceroute；根因请使用 ``BusinessPathAnalyzer`` 或 ``RootCauseEngine``。

    多 ``BizDomainPortSpec`` 在 ``run_business_domain_port_probes`` 内**并行**调度，缩短多目标总耗时。

    Traceroute 结果写入每行 ``trace``；**不**参与 ``aggregate_error`` 与联合门控（见
    ``business_host_probe.run_business_domain_port_probes`` 说明）。

    Args:
        ctx: 流程上下文（需含 ``trace_id``）。
        targets: ``BizDomainPortSpec`` 列表。
        dns_server: 可选自定义 DNS IPv4。
        dispatcher: 工具调度器；默认新建 ``ToolDispatcher()``。
        max_addrs_per_domain: 每域名最多探测的 A 记录数。
        tcp_count: 每次 tcping 次数。
        tcp_timeout: DNS/TCP 超时秒数。
        compare_system_dns: 为真且 ``dns_server`` 非空时，额外以系统解析对照并写入 ``dns_comparison``。
        enable_traceroute: 为假时跳过本机路由追踪（``trace`` 为空列表）。
        traceroute_max_hops: 路由追踪最大跳数。
        traceroute_timeout: 每跳超时（秒），传入 ``TraceRouteTool``。
        traceroute_protocol: ``icmp`` / ``udp`` / ``tcp``。

    Returns:
        ``BusinessDiagnosisOutcome``：含原始行与聚合错误。
    """
    disp = dispatcher if dispatcher is not None else ToolDispatcher()
    rows, agg = await run_business_domain_port_probes(
        ctx,
        targets,
        dns_server,
        disp,
        max_addrs_per_domain=max_addrs_per_domain,
        tcp_count=tcp_count,
        tcp_timeout=tcp_timeout,
        compare_system_dns=compare_system_dns,
        enable_traceroute=enable_traceroute,
        traceroute_max_hops=traceroute_max_hops,
        traceroute_timeout=traceroute_timeout,
        traceroute_protocol=traceroute_protocol,
        on_biz_ips_ready=on_biz_ips_ready,
        on_tcp_probe_done=on_tcp_probe_done,
    )
    status = "partial" if agg else "ok"
    return BusinessDiagnosisOutcome(
        status=status,
        business_probes=list(rows),
        aggregate_error=agg,
    )
