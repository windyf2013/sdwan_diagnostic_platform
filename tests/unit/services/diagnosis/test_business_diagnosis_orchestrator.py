"""Orchestrator returns probes only; analyzer is separate (see RootCauseEngine / CLI)."""

import pytest

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.services.diagnosis.business_diagnosis import (
    orchestrate_business_domain_port_diagnosis,
)
from sdwan_desktop.services.probe.business_host_probe import BizDomainPortSpec
from sdwan_desktop.tools.registry.base import ToolDispatcher


class _FakeDispatcher(ToolDispatcher):
    def __init__(self, script: dict) -> None:
        super().__init__()
        self.script = script

    async def dispatch(self, tool_name: str, request: ToolRequest, ctx: FlowContext) -> ToolResponse:
        params = request.parameters or {}
        key = (tool_name, str(params.get("domain") or params.get("host") or ""))
        if key in self.script:
            return self.script[key]
        return ToolResponse(success=False, error_message="unscripted")


@pytest.mark.asyncio
async def test_orchestrate_returns_status_and_rows() -> None:
    ctx = FlowContext(trace_id="t-orch-1")
    script = {
        ("dns", "x.example"): ToolResponse(
            success=True,
            data={"resolved_ips": ["198.51.100.1"], "dns_server_used": None, "response_time_ms": 1},
        ),
        ("tcping", "198.51.100.1"): ToolResponse(
            success=True,
            data={"port_open": True, "response_time_avg": 1.0, "loss_rate": 0.0},
        ),
        ("traceroute", "198.51.100.1"): ToolResponse(
            success=True,
            data={
                "success": True,
                "hops": [{"hop": 1, "ip": "10.1.1.1", "rtts": [1.0, 1.0, 1.0]}],
                "total_hops": 1,
                "target_reached": False,
                "target_ip": None,
            },
        ),
    }
    d = _FakeDispatcher(script)
    out = await orchestrate_business_domain_port_diagnosis(
        ctx,
        [BizDomainPortSpec(domain="x.example", port=443)],
        None,
        d,
    )
    assert out.status == "ok"
    assert out.aggregate_error is None
    assert len(out.business_probes) == 1
    assert out.business_probes[0]["domain"] == "x.example"
    assert len(out.business_probes[0].get("trace") or []) == 1
