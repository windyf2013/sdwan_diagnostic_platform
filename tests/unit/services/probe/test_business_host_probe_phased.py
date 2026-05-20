"""三阶段 probe：TCP 完成后、traceroute 前 notify。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.tool import ToolResponse
from sdwan_desktop.services.probe.business_host_probe import (
    BizDomainPortSpec,
    run_business_domain_port_probes,
)


@pytest.mark.asyncio
async def test_phased_probe_tcp_notify_before_traceroute() -> None:
    ctx = FlowContext(trace_id="phased-1")
    order: list[str] = []

    async def on_biz_ips_ready(_ips: list[str]) -> None:
        order.append("dns_ready")

    async def on_tcp_probe_done(_ips: list[str]) -> None:
        order.append("tcp_done")

    dispatcher = MagicMock()

    async def dispatch(tool_name: str, request=None, ctx=None, **_k):
        host = (request.parameters or {}).get("host", "")
        if tool_name == "dns":
            return ToolResponse(
                success=True,
                data={"resolved_ips": ["1.1.1.1"], "dns_server_used": "8.8.8.8"},
                trace_id=ctx.trace_id,
            )
        if tool_name == "tcping":
            order.append("tcping")
            return ToolResponse(
                success=True,
                data={"port_open": True, "response_time_avg": 1.0, "loss_rate": 0.0},
                trace_id=ctx.trace_id,
            )
        if tool_name == "traceroute":
            order.append("traceroute")
            return ToolResponse(success=True, data={"hops": [], "total_hops": 0, "target_reached": False})
        return ToolResponse(success=False, error_message="unknown")

    dispatcher.dispatch = AsyncMock(side_effect=dispatch)

    rows, err = await run_business_domain_port_probes(
        ctx,
        [BizDomainPortSpec(domain="a.com", port=443)],
        None,
        dispatcher,
        on_biz_ips_ready=on_biz_ips_ready,
        on_tcp_probe_done=on_tcp_probe_done,
    )
    assert err is None
    assert rows[0]["dns"]["status"] == "ok"
    assert order.index("tcp_done") < order.index("traceroute")
    assert order.index("dns_ready") < order.index("tcping")
