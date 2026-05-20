"""business_joint_runtime_coordinator 时序与 notify-only 回调。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.services.diagnosis.business_joint_runtime_coordinator import (
    orchestrate_business_probe_with_parallel_cpe_collect,
)
from sdwan_desktop.services.probe.business_host_probe import BizDomainPortSpec


@pytest.mark.asyncio
async def test_tcp_notify_fires_before_traceroute_dispatch() -> None:
    ctx = FlowContext(trace_id="t1")
    order: list[str] = []

    async def fake_orchestrate(*_a, on_biz_ips_ready=None, on_tcp_probe_done=None, **_k):
        if on_biz_ips_ready:
            await on_biz_ips_ready(["1.1.1.1"])
        order.append("tcp_start")
        if on_tcp_probe_done:
            await on_tcp_probe_done(["1.1.1.1"])
        order.append("tcp_done")
        order.append("trace")
        from sdwan_desktop.services.diagnosis.business_diagnosis import BusinessDiagnosisOutcome

        return BusinessDiagnosisOutcome(status="ok", business_probes=[], aggregate_error=None)

    collector = MagicMock()
    collector.prepare_session = AsyncMock(return_value=MagicMock(success=True))
    collector.run_commands_on_open_session = AsyncMock(return_value={})
    collector.collect_on_open_session = AsyncMock(
        return_value=MagicMock(success=True, data={"raw_outputs": {}, "device_type": "raisecom_msg5200b"})
    )
    collector.release_session = AsyncMock()
    collector._raw_outputs = {}
    collector._active_device_type = "raisecom_msg5200b"

    async def track_run(*args, **kwargs):
        order.append("cpe_cmds")
        return {}

    collector.run_commands_on_open_session.side_effect = track_run

    with patch(
        "sdwan_desktop.services.diagnosis.business_joint_runtime_coordinator.orchestrate_business_domain_port_diagnosis",
        side_effect=fake_orchestrate,
    ):
        outcome, task = await orchestrate_business_probe_with_parallel_cpe_collect(
            ctx,
            [BizDomainPortSpec(domain="a.com", port=443)],
            None,
            cpe_collector=collector,
        )
        await task

    assert order.index("tcp_done") < order.index("trace")
    assert outcome.status == "ok"
