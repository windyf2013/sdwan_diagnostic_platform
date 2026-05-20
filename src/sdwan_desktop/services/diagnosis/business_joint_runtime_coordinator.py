"""business-diagnose 联合模式：PC 探测与 CPE 单次会话并行采集（baseline/post conntrack）。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional, Sequence, Tuple

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.collector.cpe_collector import CpeCollector
from sdwan_desktop.services.diagnosis.business_diagnosis import (
    BusinessDiagnosisOutcome,
    orchestrate_business_domain_port_diagnosis,
)
from sdwan_desktop.services.probe.business_host_probe import BizDomainPortSpec
from sdwan_desktop.services.probe.planner import (
    plan_baseline_conntrack_commands,
    plan_post_topology_probe_commands,
    plan_runtime_probe_commands,
)

logger = logging.getLogger(__name__)

_CPE_EVENT_TIMEOUT = 300.0


async def _run_parallel_cpe_collect(
    ctx: FlowContext,
    cpe_collector: CpeCollector,
    biz_ips_ready: asyncio.Event,
    tcp_probe_done: asyncio.Event,
    shared_ips: List[str],
) -> None:
    """Task_cpe：单次建连；baseline → post/runtime → 全量采集。"""
    start_time = None
    try:
        cpe_collector._raw_outputs = {}
        cpe_collector._active_device_type = None
        prep = await cpe_collector.prepare_session(ctx)
        if not prep.success:
            ctx.set(
                "cpe_result",
                CollectorResult(
                    success=False,
                    error_message=prep.error_message or "CPE 会话准备失败",
                ),
            )
            return

        try:
            await asyncio.wait_for(biz_ips_ready.wait(), timeout=_CPE_EVENT_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("CPE 并行采集：等待 DNS/biz_ips_ready 超时")
            ctx.set(
                "cpe_result",
                CollectorResult(
                    success=False,
                    error_message="等待业务 DNS 就绪超时",
                ),
            )
            await cpe_collector.release_session()
            return

        ips = list(dict.fromkeys(shared_ips))
        baseline_cmds = plan_baseline_conntrack_commands(ips)
        if baseline_cmds:
            await cpe_collector.run_commands_on_open_session(baseline_cmds)

        try:
            await asyncio.wait_for(tcp_probe_done.wait(), timeout=_CPE_EVENT_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("CPE 并行采集：等待 TCP 探测完成超时")
            await cpe_collector.release_session()
            ctx.set(
                "cpe_result",
                CollectorResult(
                    success=False,
                    error_message="等待 TCP 探测完成超时",
                    data={"raw_outputs": dict(cpe_collector._raw_outputs)},
                ),
            )
            return

        device_type = str(ctx.get("cpe_device_type") or cpe_collector._active_device_type or "generic")
        runtime_cmds = plan_runtime_probe_commands(device_type, ips)
        if runtime_cmds:
            await cpe_collector.run_commands_on_open_session(runtime_cmds)

        import time

        start_time = time.time()
        skip_keys = set(cpe_collector._raw_outputs.keys())
        post_cmds = plan_post_topology_probe_commands(
            device_type,
            biz_target_ips=ips,
            include_tunnel_peer_probes=False,
            skip_keys=skip_keys,
        )
        if post_cmds:
            await cpe_collector.run_commands_on_open_session(post_cmds, skip_keys=skip_keys)

        result = await cpe_collector.collect_on_open_session(
            ctx,
            start_time=start_time,
            skip_keys=set(cpe_collector._raw_outputs.keys()),
        )
        ctx.set("cpe_result", result)
    except asyncio.CancelledError:
        logger.info("CPE 并行采集任务已取消")
        try:
            await cpe_collector.release_session()
        except Exception:
            pass
        raise
    except Exception as exc:
        logger.error("CPE 并行采集失败: %s", exc, exc_info=True)
        try:
            await cpe_collector.release_session()
        except Exception:
            pass
        from sdwan_desktop.services.collector.base import CollectorResult

        ctx.set(
            "cpe_result",
            CollectorResult(
                success=False,
                error_message=str(exc),
                data={"raw_outputs": dict(getattr(cpe_collector, "_raw_outputs", {}) or {})},
            ),
        )


async def orchestrate_business_probe_with_parallel_cpe_collect(
    ctx: FlowContext,
    targets: Sequence[BizDomainPortSpec],
    dns_server: Optional[str],
    *,
    cpe_collector: CpeCollector,
    compare_system_dns: bool = False,
    enable_traceroute: bool = True,
) -> Tuple[BusinessDiagnosisOutcome, asyncio.Task[None]]:
    """PC 三阶段探测与 CPE 单次会话采集并行；回调仅 notify（set Event）。"""
    biz_ips_ready = asyncio.Event()
    tcp_probe_done = asyncio.Event()
    shared_ips: List[str] = []

    async def _on_biz_ips_ready(ips: List[str]) -> None:
        shared_ips.clear()
        shared_ips.extend(ips)
        biz_ips_ready.set()

    async def _on_tcp_probe_done(_ips: List[str]) -> None:
        tcp_probe_done.set()

    cpe_task = asyncio.create_task(
        _run_parallel_cpe_collect(
            ctx,
            cpe_collector,
            biz_ips_ready,
            tcp_probe_done,
            shared_ips,
        )
    )
    ctx.set("_parallel_cpe_task", cpe_task)

    outcome = await orchestrate_business_domain_port_diagnosis(
        ctx,
        targets,
        dns_server,
        None,
        compare_system_dns=compare_system_dns,
        enable_traceroute=enable_traceroute,
        on_biz_ips_ready=_on_biz_ips_ready,
        on_tcp_probe_done=_on_tcp_probe_done,
    )
    return outcome, cpe_task


async def await_parallel_cpe_collect(
    cpe_task: Optional[asyncio.Task[None]],
    *,
    cancel: bool = False,
) -> None:
    """等待或取消并行 CPE 采集任务。"""
    if cpe_task is None:
        return
    if cancel:
        cpe_task.cancel()
        try:
            await cpe_task
        except asyncio.CancelledError:
            pass
        return
    await cpe_task
