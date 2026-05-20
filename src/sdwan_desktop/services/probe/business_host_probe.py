"""PC 侧业务级探测：域名 DNS(A) + 解析地址 TCP 端口 + 可选 ICMP 路径追踪。

多域名之间**并行**执行（``asyncio.gather``），单域名内 DNS→TCP→traceroute 仍顺序执行。

编排入口见 ``sdwan_desktop.services.diagnosis.business_diagnosis.orchestrate_business_domain_port_diagnosis``；
经 ``ToolDispatcher`` 调用已注册的 ``dns`` / ``tcping`` / ``traceroute``。

**联合诊断门控（产品语义）**：是否要求 CPE 联合仍以 **DNS + TCP** 为准；``traceroute`` 失败或
「未到达目标」**不**写入 ``aggregate_error``，避免 ICMP 与 TCP 路径不一致导致误触发联合。
详见 ``spec/detail_function_design.md`` §2.2.2 与 ``business_diagnose_followup.business_probe_requires_joint_diagnosis``。
"""

from __future__ import annotations

import asyncio
import copy
import ipaddress
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.tools.registry.base import ToolDispatcher

logger = logging.getLogger(__name__)

# 业务探测默认预算（与 ``business_diagnosis.orchestrate_*`` 共用，避免编排层与探针层默认漂移）
DEFAULT_MAX_ADDRS_PER_DOMAIN = 4
DEFAULT_TCP_COUNT = 1
DEFAULT_TCP_TIMEOUT = 5
DEFAULT_TRACEROUTE_MAX_HOPS = 12
DEFAULT_TRACEROUTE_TIMEOUT = 2
DEFAULT_TRACEROUTE_PROTOCOL = "icmp"


@dataclass(slots=True)
class BizDomainPortSpec:
    """用户指定的业务探测目标（FQDN + TCP 端口）。"""

    domain: str
    port: int


def parse_biz_target_tokens(tokens: Sequence[str]) -> List[BizDomainPortSpec]:
    """解析 ``--biz-target`` 形如 ``example.com:443``；无 ``:port`` 时默认端口 443。

    Args:
        tokens: CLI 多次传入的原始字符串。

    Returns:
        解析后的规格列表。

    Raises:
        ValueError: 端口非法或字符串为空。
    """
    out: List[BizDomainPortSpec] = []
    for raw in tokens:
        s = (raw or "").strip()
        if not s:
            raise ValueError("biz-target 不能为空字符串")
        domain, port = _parse_one_biz_target(s)
        out.append(BizDomainPortSpec(domain=domain, port=port))
    return out


def _parse_one_biz_target(s: str) -> Tuple[str, int]:
    """从 ``host:port`` 拆出域名与端口（仅支持末尾 ``:port`` 形式）。"""
    if ":" in s:
        host_part, port_part = s.rsplit(":", 1)
        host_part = host_part.strip()
        port_part = port_part.strip()
        if port_part.isdigit():
            p = int(port_part)
            if 1 <= p <= 65535:
                if not host_part:
                    raise ValueError(f"biz-target 格式无效: {s!r}")
                return host_part, p
    return s.strip(), 443


def _ipv4_only(ips: Sequence[str]) -> List[str]:
    """仅保留可解析为 IPv4 的地址，去重且保序。"""
    seen: set[str] = set()
    ordered: List[str] = []
    for ip in ips:
        ip = (ip or "").strip()
        if not ip or ip in seen:
            continue
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if isinstance(addr, ipaddress.IPv4Address):
            seen.add(ip)
            ordered.append(ip)
    return ordered


def _dns_comparison_payload(
    system_block: Dict[str, Any],
    custom_block: Dict[str, Any],
) -> Dict[str, Any]:
    """系统 DNS 与显式 DNS 的 IPv4 A 列表是否不一致。"""
    s_ips: List[str] = []
    c_ips: List[str] = []
    if system_block.get("status") == "ok" and isinstance(system_block.get("data"), dict):
        s_ips = _ipv4_only((system_block["data"] or {}).get("resolved_ips") or [])
    if custom_block.get("status") == "ok" and isinstance(custom_block.get("data"), dict):
        c_ips = _ipv4_only((custom_block["data"] or {}).get("resolved_ips") or [])
    split_v4 = bool(s_ips and c_ips and s_ips != c_ips)
    return {
        "system": system_block,
        "custom": copy.deepcopy(custom_block),
        "split_v4": split_v4,
    }


async def _dns_query_a(
    ctx: FlowContext,
    domain: str,
    dns_server: Optional[str],
    dispatcher: ToolDispatcher,
    timeout: int,
) -> Dict[str, Any]:
    """执行单次 A 记录查询，返回与 ``business_probes`` 行内 ``dns`` 同形字典。"""
    dns_params: Dict[str, Any] = {
        "domain": domain,
        "record_type": "A",
        "timeout": timeout,
    }
    if dns_server:
        dns_params["dns_server"] = dns_server
    dns_req = ToolRequest(
        tool_name="dns",
        parameters=dns_params,
        trace_id=ctx.trace_id,
    )
    try:
        dns_resp: ToolResponse = await dispatcher.dispatch(
            tool_name="dns",
            request=dns_req,
            ctx=ctx,
        )
    except Exception as exc:
        logger.warning("DNS 查询异常 %s: %s", domain, exc)
        return {"status": "error", "data": None, "error": str(exc)}
    if not dns_resp.success:
        return {
            "status": "error",
            "data": dns_resp.data,
            "error": dns_resp.error_message or dns_resp.error_code,
        }
    resolved = _ipv4_only((dns_resp.data or {}).get("resolved_ips") or [])
    block: Dict[str, Any] = {
        "status": "ok",
        "data": {
            "resolved_ips": resolved,
            "dns_server_used": (dns_resp.data or {}).get("dns_server_used"),
            "response_time_ms": (dns_resp.data or {}).get("response_time_ms"),
        },
        "error": None,
    }
    if not resolved:
        block["status"] = "no_a"
        block["error"] = "无 IPv4 A 记录"
    return block


def _trace_entry_from_tool_response(
    host: str,
    business_port: int,
    resp: ToolResponse,
) -> Dict[str, Any]:
    """将 ``traceroute`` 工具响应规范为 ``business_probes[].trace`` 单行结构。"""
    entry: Dict[str, Any] = {
        "host": host,
        "port": business_port,
    }
    if resp.success and isinstance(resp.data, dict):
        raw = resp.data
        hops = raw.get("hops") if isinstance(raw.get("hops"), list) else []
        total = int(raw.get("total_hops") or len(hops))
        target_reached = bool(raw.get("target_reached"))
        summary: Dict[str, Any] = {
            "target_reached": target_reached,
            "total_hops": total,
            "target_ip": raw.get("target_ip"),
        }
        if hops:
            last = hops[-1]
            if isinstance(last, dict) and last.get("ip") not in (None, "", "*"):
                summary["last_hop_ip"] = last.get("ip")
        entry["status"] = "ok"
        entry["data"] = {"summary": summary, "hops": hops}
        entry["error"] = None
        return entry
    entry["status"] = "error"
    entry["data"] = None
    entry["error"] = resp.error_message or resp.error_code or "traceroute failed"
    return entry


async def _run_traceroute_to_host(
    ctx: FlowContext,
    host: str,
    dispatcher: ToolDispatcher,
    *,
    max_hops: int,
    per_hop_timeout: int,
    protocol: str,
) -> ToolResponse:
    """对单 IPv4 执行路由追踪；异常封装为 ``ToolResponse(success=False)``。"""
    tr_req = ToolRequest(
        tool_name="traceroute",
        parameters={
            "host": host,
            "max_hops": max_hops,
            "timeout": per_hop_timeout,
            "protocol": protocol,
        },
        trace_id=ctx.trace_id,
    )
    try:
        return await dispatcher.dispatch(
            tool_name="traceroute",
            request=tr_req,
            ctx=ctx,
        )
    except Exception as exc:
        logger.warning("traceroute 调度异常 %s: %s", host, exc)
        return ToolResponse(
            success=False,
            error_message=str(exc),
            trace_id=ctx.trace_id,
        )


async def _probe_dns_only(
    ctx: FlowContext,
    spec: BizDomainPortSpec,
    dns_server: Optional[str],
    dispatcher: ToolDispatcher,
    tcp_timeout: int,
    *,
    compare_system_dns: bool,
) -> Tuple[Dict[str, Any], List[str]]:
    """单域名 DNS 阶段；返回行骨架与错误片段。"""
    err_parts: List[str] = []
    row: Dict[str, Any] = {
        "domain": spec.domain,
        "port": spec.port,
        "dns": {"status": "pending", "data": None, "error": None},
        "tcp": [],
        "trace": [],
    }
    system_block: Optional[Dict[str, Any]] = None
    if compare_system_dns and dns_server:
        system_block = await _dns_query_a(ctx, spec.domain, None, dispatcher, tcp_timeout)

    row["dns"] = await _dns_query_a(ctx, spec.domain, dns_server, dispatcher, tcp_timeout)
    if system_block is not None:
        row["dns_comparison"] = _dns_comparison_payload(system_block, row["dns"])

    if row["dns"]["status"] == "error":
        err_parts.append(f"{spec.domain}: dns {row['dns'].get('error')}")
    elif row["dns"]["status"] == "no_a":
        err_parts.append(f"{spec.domain}: 无 IPv4 A 记录")
    return row, err_parts


async def _probe_tcp_for_row(
    ctx: FlowContext,
    row: Dict[str, Any],
    spec: BizDomainPortSpec,
    dispatcher: ToolDispatcher,
    max_addrs_per_domain: int,
    tcp_count: int,
    tcp_timeout: int,
) -> List[str]:
    """对已有 DNS 行的域名执行 TCP；返回错误片段。"""
    err_parts: List[str] = []
    if row["dns"]["status"] not in ("ok",):
        return err_parts
    resolved = _ipv4_only((row["dns"].get("data") or {}).get("resolved_ips") or [])
    row["tcp"] = []
    for ip in resolved[:max_addrs_per_domain]:
        tcp_req = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": ip,
                "port": spec.port,
                "count": tcp_count,
                "timeout": tcp_timeout,
            },
            trace_id=ctx.trace_id,
        )
        tcp_entry: Dict[str, Any] = {"host": ip, "port": spec.port}
        try:
            tcp_resp: ToolResponse = await dispatcher.dispatch(
                tool_name="tcping",
                request=tcp_req,
                ctx=ctx,
            )
        except Exception as exc:
            logger.warning("TCP 探测失败 %s:%s %s", ip, spec.port, exc)
            tcp_entry["status"] = "error"
            tcp_entry["error"] = str(exc)
            err_parts.append(f"{spec.domain}@{ip}:{spec.port} tcp {exc}")
            row["tcp"].append(tcp_entry)
            continue

        if tcp_resp.success and tcp_resp.data:
            tcp_entry["status"] = "ok"
            tcp_entry["data"] = {
                "port_open": tcp_resp.data.get("port_open"),
                "response_time_avg": tcp_resp.data.get("response_time_avg"),
                "loss_rate": tcp_resp.data.get("loss_rate"),
            }
        else:
            tcp_entry["status"] = "error"
            tcp_entry["error"] = tcp_resp.error_message or tcp_resp.error_code
            err_parts.append(f"{spec.domain}@{ip}:{spec.port} tcp {tcp_entry['error']}")
        row["tcp"].append(tcp_entry)
    return err_parts


async def _probe_trace_for_row(
    ctx: FlowContext,
    row: Dict[str, Any],
    spec: BizDomainPortSpec,
    dispatcher: ToolDispatcher,
    *,
    enable_traceroute: bool,
    traceroute_max_hops: int,
    traceroute_timeout: int,
    traceroute_protocol: str,
) -> None:
    """对已有 DNS 行的域名执行 traceroute（旁证）。"""
    row["trace"] = []
    if not enable_traceroute or row["dns"]["status"] != "ok":
        return
    resolved = _ipv4_only((row["dns"].get("data") or {}).get("resolved_ips") or [])
    if not resolved:
        return
    trace_host = resolved[0]
    tr_resp = await _run_traceroute_to_host(
        ctx,
        trace_host,
        dispatcher,
        max_hops=traceroute_max_hops,
        per_hop_timeout=traceroute_timeout,
        protocol=traceroute_protocol,
    )
    if not tr_resp.success:
        logger.info(
            "业务探测 traceroute 未成功（不计入 aggregate_error）: %s %s",
            trace_host,
            tr_resp.error_message,
        )
    row["trace"].append(_trace_entry_from_tool_response(trace_host, spec.port, tr_resp))


def _resolved_ips_from_rows(rows: Sequence[Dict[str, Any]]) -> List[str]:
    ips: List[str] = []
    for row in rows:
        dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
        if dns.get("status") == "ok":
            data = dns.get("data") if isinstance(dns.get("data"), dict) else {}
            ips.extend(_ipv4_only(data.get("resolved_ips") or []))
    return list(dict.fromkeys(ips))


async def _run_phased_business_probes(
    ctx: FlowContext,
    targets: Sequence[BizDomainPortSpec],
    dns_server: Optional[str],
    dispatcher: ToolDispatcher,
    max_addrs_per_domain: int,
    tcp_count: int,
    tcp_timeout: int,
    *,
    compare_system_dns: bool,
    enable_traceroute: bool,
    traceroute_max_hops: int,
    traceroute_timeout: int,
    traceroute_protocol: str,
    on_biz_ips_ready: Callable[[List[str]], Awaitable[None]],
    on_tcp_probe_done: Callable[[List[str]], Awaitable[None]],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """联合诊断：全局 DNS → notify → 全局 TCP → notify → 全局 traceroute。"""
    err_parts: List[str] = []
    rows: List[Dict[str, Any]] = []

    dns_pairs = await asyncio.gather(
        *[
            _probe_dns_only(
                ctx,
                spec,
                dns_server,
                dispatcher,
                tcp_timeout,
                compare_system_dns=compare_system_dns,
            )
            for spec in targets
        ]
    )
    for row, errs in dns_pairs:
        rows.append(row)
        err_parts.extend(errs)

    all_ips = _resolved_ips_from_rows(rows)
    await on_biz_ips_ready(all_ips)

    tcp_tasks = [
        _probe_tcp_for_row(
            ctx,
            rows[i],
            targets[i],
            dispatcher,
            max_addrs_per_domain,
            tcp_count,
            tcp_timeout,
        )
        for i in range(len(targets))
    ]
    tcp_err_lists = await asyncio.gather(*tcp_tasks)
    for errs in tcp_err_lists:
        err_parts.extend(errs)

    await on_tcp_probe_done(all_ips)

    await asyncio.gather(
        *[
            _probe_trace_for_row(
                ctx,
                rows[i],
                targets[i],
                dispatcher,
                enable_traceroute=enable_traceroute,
                traceroute_max_hops=traceroute_max_hops,
                traceroute_timeout=traceroute_timeout,
                traceroute_protocol=traceroute_protocol,
            )
            for i in range(len(targets))
        ]
    )

    agg_err = "; ".join(err_parts) if err_parts else None
    return rows, agg_err


async def _probe_one_business_domain(
    ctx: FlowContext,
    spec: BizDomainPortSpec,
    dns_server: Optional[str],
    dispatcher: ToolDispatcher,
    max_addrs_per_domain: int,
    tcp_count: int,
    tcp_timeout: int,
    *,
    compare_system_dns: bool,
    enable_traceroute: bool,
    traceroute_max_hops: int,
    traceroute_timeout: int,
    traceroute_protocol: str,
) -> Tuple[Dict[str, Any], List[str]]:
    """单域名完整链：DNS(A) → 多地址 TCP → 可选 traceroute；返回一行与 DNS/TCP 聚合错误片段。"""
    err_parts: List[str] = []
    row: Dict[str, Any] = {
        "domain": spec.domain,
        "port": spec.port,
        "dns": {"status": "pending", "data": None, "error": None},
        "tcp": [],
        "trace": [],
    }
    system_block: Optional[Dict[str, Any]] = None
    if compare_system_dns and dns_server:
        system_block = await _dns_query_a(
            ctx, spec.domain, None, dispatcher, tcp_timeout
        )

    row["dns"] = await _dns_query_a(
        ctx, spec.domain, dns_server, dispatcher, tcp_timeout
    )

    if system_block is not None:
        row["dns_comparison"] = _dns_comparison_payload(system_block, row["dns"])

    if row["dns"]["status"] == "error":
        err_parts.append(f"{spec.domain}: dns {row['dns'].get('error')}")
        return row, err_parts

    if row["dns"]["status"] == "no_a":
        err_parts.append(f"{spec.domain}: 无 IPv4 A 记录")
        return row, err_parts

    resolved = _ipv4_only((row["dns"].get("data") or {}).get("resolved_ips") or [])

    for ip in resolved[:max_addrs_per_domain]:
        tcp_req = ToolRequest(
            tool_name="tcping",
            parameters={
                "host": ip,
                "port": spec.port,
                "count": tcp_count,
                "timeout": tcp_timeout,
            },
            trace_id=ctx.trace_id,
        )
        tcp_entry: Dict[str, Any] = {"host": ip, "port": spec.port}
        try:
            tcp_resp: ToolResponse = await dispatcher.dispatch(
                tool_name="tcping",
                request=tcp_req,
                ctx=ctx,
            )
        except Exception as exc:
            logger.warning("TCP 探测失败 %s:%s %s", ip, spec.port, exc)
            tcp_entry["status"] = "error"
            tcp_entry["error"] = str(exc)
            err_parts.append(f"{spec.domain}@{ip}:{spec.port} tcp {exc}")
            row["tcp"].append(tcp_entry)
            continue

        if tcp_resp.success and tcp_resp.data:
            tcp_entry["status"] = "ok"
            tcp_entry["data"] = {
                "port_open": tcp_resp.data.get("port_open"),
                "response_time_avg": tcp_resp.data.get("response_time_avg"),
                "loss_rate": tcp_resp.data.get("loss_rate"),
            }
        else:
            tcp_entry["status"] = "error"
            tcp_entry["error"] = tcp_resp.error_message or tcp_resp.error_code
            err_parts.append(f"{spec.domain}@{ip}:{spec.port} tcp {tcp_entry['error']}")
        row["tcp"].append(tcp_entry)

    # 路径旁证：每域名仅对首个 IPv4 A 记录追踪一次，避免多 A 记录时重复 traceroute。
    if enable_traceroute and resolved:
        trace_host = resolved[0]
        tr_resp = await _run_traceroute_to_host(
            ctx,
            trace_host,
            dispatcher,
            max_hops=traceroute_max_hops,
            per_hop_timeout=traceroute_timeout,
            protocol=traceroute_protocol,
        )
        if not tr_resp.success:
            logger.info(
                "业务探测 traceroute 未成功（不计入 aggregate_error）: %s %s",
                trace_host,
                tr_resp.error_message,
            )
        row["trace"].append(
            _trace_entry_from_tool_response(trace_host, spec.port, tr_resp)
        )

    return row, err_parts


async def run_business_domain_port_probes(
    ctx: FlowContext,
    targets: Sequence[BizDomainPortSpec],
    dns_server: Optional[str],
    dispatcher: ToolDispatcher,
    max_addrs_per_domain: int = DEFAULT_MAX_ADDRS_PER_DOMAIN,
    tcp_count: int = DEFAULT_TCP_COUNT,
    tcp_timeout: int = DEFAULT_TCP_TIMEOUT,
    *,
    compare_system_dns: bool = False,
    enable_traceroute: bool = True,
    traceroute_max_hops: int = DEFAULT_TRACEROUTE_MAX_HOPS,
    traceroute_timeout: int = DEFAULT_TRACEROUTE_TIMEOUT,
    traceroute_protocol: str = DEFAULT_TRACEROUTE_PROTOCOL,
    on_biz_ips_ready: Optional[Callable[[List[str]], Awaitable[None]]] = None,
    on_tcp_probe_done: Optional[Callable[[List[str]], Awaitable[None]]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """在 PC 侧对多个 ``域名:端口`` 执行 DNS(A)、TCP 握手与可选 ICMP 路径追踪。

    **多域名并行**：不同 ``BizDomainPortSpec`` 之间通过 ``asyncio.gather`` 并发执行各自
    DNS→TCP→traceroute 链，以缩短多目标（如 baidu/youtube/tiktok）总墙钟时间；同一域名内
    多 A 记录仍为 TCP 串行、traceroute 仅首 A 一次（与原先一致）。

    Args:
        ctx: 流程上下文（``trace_id``）。
        targets: 业务目标列表。
        dns_server: 可选，传给 ``dns`` 工具的 ``dns_server``。
        dispatcher: 工具调度器。
        max_addrs_per_domain: 每个域名最多对若干 A 记录做 TCP；traceroute 仅对首个 A 记录执行一次（路径旁证）。
        tcp_count: 每次 ``tcping`` 探测次数。
        tcp_timeout: DNS/TCP 单次相关超时（秒）；DNS 查询复用该值。
        compare_system_dns: 为真且 ``dns_server`` 非空时写入 ``dns_comparison``。
        enable_traceroute: 为假时跳过 ``traceroute``（``trace`` 为空列表）。
        traceroute_max_hops: 路由追踪最大跳数（默认收紧以控制总耗时）。
        traceroute_timeout: 传入工具的每跳超时（秒），语义见 ``TraceRouteTool``。
        traceroute_protocol: ``icmp`` / ``udp`` / ``tcp``，默认 ``icmp``（与现网 Windows/Linux 工具链一致）。

    Returns:
        (各行可 JSON 化的结果列表, 聚合错误信息或 ``None``)。聚合错误**仅**含 DNS/TCP 关键失败。
        行顺序与 ``targets`` 顺序一致。
    """
    if not targets:
        return [], None

    if on_biz_ips_ready is not None and on_tcp_probe_done is not None:
        return await _run_phased_business_probes(
            ctx,
            targets,
            dns_server,
            dispatcher,
            max_addrs_per_domain,
            tcp_count,
            tcp_timeout,
            compare_system_dns=compare_system_dns,
            enable_traceroute=enable_traceroute,
            traceroute_max_hops=traceroute_max_hops,
            traceroute_timeout=traceroute_timeout,
            traceroute_protocol=traceroute_protocol,
            on_biz_ips_ready=on_biz_ips_ready,
            on_tcp_probe_done=on_tcp_probe_done,
        )

    tasks = [
        _probe_one_business_domain(
            ctx,
            spec,
            dns_server,
            dispatcher,
            max_addrs_per_domain,
            tcp_count,
            tcp_timeout,
            compare_system_dns=compare_system_dns,
            enable_traceroute=enable_traceroute,
            traceroute_max_hops=traceroute_max_hops,
            traceroute_timeout=traceroute_timeout,
            traceroute_protocol=traceroute_protocol,
        )
        for spec in targets
    ]
    pairs = await asyncio.gather(*tasks)
    rows = [p[0] for p in pairs]
    err_parts: List[str] = []
    for _row, errs in pairs:
        err_parts.extend(errs)

    agg_err = "; ".join(err_parts) if err_parts else None
    return rows, agg_err
