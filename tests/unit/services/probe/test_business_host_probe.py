"""Unit tests for business_host_probe (DNS A + TCP + optional traceroute by domain:port)."""

from __future__ import annotations

from typing import Any

import pytest

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.services.probe.business_host_probe import (
    BizDomainPortSpec,
    parse_biz_target_tokens,
    run_business_domain_port_probes,
)
from sdwan_desktop.tools.registry.base import ToolDispatcher


class _FakeDispatcher(ToolDispatcher):
    """Returns scripted DNS / tcping / traceroute responses without registering real tools."""

    def __init__(self, script: dict[tuple[str, str], ToolResponse]) -> None:
        super().__init__()
        self.script = script
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def dispatch(
        self,
        tool_name: str,
        request: ToolRequest,
        ctx: FlowContext,
    ) -> ToolResponse:
        params = request.parameters or {}
        key = (tool_name, str(params.get("domain") or params.get("host") or ""))
        self.calls.append((tool_name, dict(params)))
        if key in self.script:
            return self.script[key]
        return ToolResponse(success=False, error_message="unscripted")


def test_parse_biz_target_tokens_default_port() -> None:
    specs = parse_biz_target_tokens(["Example.COM", "x:8080"])
    assert specs == [
        BizDomainPortSpec(domain="Example.COM", port=443),
        BizDomainPortSpec(domain="x", port=8080),
    ]


def test_parse_biz_target_tokens_empty_iterable() -> None:
    assert parse_biz_target_tokens(()) == []


def test_parse_biz_target_tokens_rejects_blank() -> None:
    with pytest.raises(ValueError, match="biz-target"):
        parse_biz_target_tokens(["  "])


_TR_HOPS = [{"hop": 1, "ip": "10.0.0.1", "rtts": [1.0, 1.0, 1.0]}]


@pytest.mark.asyncio
async def test_run_business_domain_port_probes_happy_path() -> None:
    ctx = FlowContext(trace_id="t-probe-1")
    script = {
        ("dns", "svc.example"): ToolResponse(
            success=True,
            data={
                "resolved_ips": ["203.0.113.10", "2001:db8::1"],
                "dns_server_used": "8.8.8.8",
                "response_time_ms": 12,
            },
        ),
        ("tcping", "203.0.113.10"): ToolResponse(
            success=True,
            data={"port_open": True, "response_time_avg": 3.1, "loss_rate": 0.0},
        ),
        ("traceroute", "203.0.113.10"): ToolResponse(
            success=True,
            data={
                "success": True,
                "hops": _TR_HOPS,
                "total_hops": 1,
                "target_reached": False,
                "target_ip": "203.0.113.10",
            },
        ),
    }
    d = _FakeDispatcher(script)
    rows, agg = await run_business_domain_port_probes(
        ctx,
        [BizDomainPortSpec(domain="svc.example", port=443)],
        dns_server="8.8.8.8",
        dispatcher=d,
        max_addrs_per_domain=4,
        tcp_count=1,
        tcp_timeout=2,
    )
    assert agg is None
    assert len(rows) == 1
    assert rows[0]["domain"] == "svc.example"
    assert rows[0]["dns"]["status"] == "ok"
    assert rows[0]["dns"]["data"]["resolved_ips"] == ["203.0.113.10"]
    assert len(rows[0]["tcp"]) == 1
    assert rows[0]["tcp"][0]["status"] == "ok"
    assert rows[0]["tcp"][0]["data"]["port_open"] is True
    assert len(rows[0]["trace"]) == 1
    assert rows[0]["trace"][0]["status"] == "ok"
    assert rows[0]["trace"][0]["data"]["summary"]["total_hops"] == 1
    assert any(c[0] == "dns" for c in d.calls)
    assert any(c[0] == "tcping" for c in d.calls)
    assert any(c[0] == "traceroute" for c in d.calls)


@pytest.mark.asyncio
async def test_run_business_domain_port_probes_no_traceroute_skips_tool() -> None:
    ctx = FlowContext(trace_id="t-probe-nt")
    script = {
        ("dns", "z.example"): ToolResponse(
            success=True,
            data={"resolved_ips": ["198.51.100.2"], "dns_server_used": None, "response_time_ms": 1},
        ),
        ("tcping", "198.51.100.2"): ToolResponse(
            success=True,
            data={"port_open": True, "response_time_avg": 1.0, "loss_rate": 0.0},
        ),
    }
    d = _FakeDispatcher(script)
    rows, agg = await run_business_domain_port_probes(
        ctx,
        [BizDomainPortSpec(domain="z.example", port=443)],
        None,
        d,
        enable_traceroute=False,
    )
    assert agg is None
    assert rows[0]["trace"] == []
    assert not any(c[0] == "traceroute" for c in d.calls)


@pytest.mark.asyncio
async def test_run_business_domain_port_probes_traceroute_error_not_in_agg() -> None:
    """Traceroute 失败不进入 aggregate_error（联合门控仍以 DNS/TCP 为准）。"""
    ctx = FlowContext(trace_id="t-probe-tr-err")
    script = {
        ("dns", "ok.example"): ToolResponse(
            success=True,
            data={"resolved_ips": ["198.51.100.3"], "dns_server_used": None, "response_time_ms": 1},
        ),
        ("tcping", "198.51.100.3"): ToolResponse(
            success=True,
            data={"port_open": True, "response_time_avg": 1.0, "loss_rate": 0.0},
        ),
        ("traceroute", "198.51.100.3"): ToolResponse(
            success=False,
            error_message="icmp admin prohibited",
        ),
    }
    d = _FakeDispatcher(script)
    rows, agg = await run_business_domain_port_probes(
        ctx,
        [BizDomainPortSpec(domain="ok.example", port=443)],
        None,
        d,
        tcp_count=1,
        tcp_timeout=2,
    )
    assert agg is None
    assert rows[0]["trace"][0]["status"] == "error"
    assert "icmp" in (rows[0]["trace"][0].get("error") or "").lower()


@pytest.mark.asyncio
async def test_run_business_domain_port_probes_traceroute_once_per_domain() -> None:
    """多 A 记录时 TCP 逐地址探测，traceroute 仅对首个 IPv4 执行一次。"""
    ctx = FlowContext(trace_id="t-probe-tr-once")
    ips = ["198.51.100.1", "198.51.100.2", "198.51.100.3"]
    script: dict[tuple[str, str], ToolResponse] = {
        ("dns", "multi.example"): ToolResponse(
            success=True,
            data={
                "resolved_ips": ips,
                "dns_server_used": None,
                "response_time_ms": 1,
            },
        ),
    }
    for ip in ips:
        script[("tcping", ip)] = ToolResponse(
            success=True,
            data={"port_open": True, "response_time_avg": 1.0, "loss_rate": 0.0},
        )
    script[("traceroute", ips[0])] = ToolResponse(
        success=True,
        data={
            "success": True,
            "hops": _TR_HOPS,
            "total_hops": 1,
            "target_reached": False,
            "target_ip": ips[0],
        },
    )
    d = _FakeDispatcher(script)
    rows, agg = await run_business_domain_port_probes(
        ctx,
        [BizDomainPortSpec(domain="multi.example", port=443)],
        None,
        d,
        max_addrs_per_domain=4,
        tcp_count=1,
    )
    assert agg is None
    assert len(rows) == 1
    assert len(rows[0]["tcp"]) == 3
    assert len(rows[0]["trace"]) == 1
    assert rows[0]["trace"][0]["host"] == ips[0]
    tr_calls = [c for c in d.calls if c[0] == "traceroute"]
    assert len(tr_calls) == 1
    assert tr_calls[0][1]["host"] == ips[0]


@pytest.mark.asyncio
async def test_run_business_domain_port_probes_three_domains_parallel_order() -> None:
    """多域名并行：结果行顺序与 targets 一致，各域独立 DNS/TCP/traceroute。"""
    ctx = FlowContext(trace_id="t-probe-3dom")
    domains = ("a.example", "b.example", "c.example")
    ips = ("198.51.100.11", "198.51.100.22", "198.51.100.33")
    script: dict[tuple[str, str], ToolResponse] = {}
    for dom, ip in zip(domains, ips, strict=True):
        script[("dns", dom)] = ToolResponse(
            success=True,
            data={
                "resolved_ips": [ip],
                "dns_server_used": None,
                "response_time_ms": 1,
            },
        )
        script[("tcping", ip)] = ToolResponse(
            success=True,
            data={"port_open": True, "response_time_avg": 1.0, "loss_rate": 0.0},
        )
        script[("traceroute", ip)] = ToolResponse(
            success=True,
            data={
                "success": True,
                "hops": _TR_HOPS,
                "total_hops": 1,
                "target_reached": False,
                "target_ip": ip,
            },
        )
    d = _FakeDispatcher(script)
    specs = [BizDomainPortSpec(domain=dom, port=443) for dom in domains]
    rows, agg = await run_business_domain_port_probes(ctx, specs, None, d, tcp_count=1, tcp_timeout=2)
    assert agg is None
    assert len(rows) == 3
    for i, dom in enumerate(domains):
        assert rows[i]["domain"] == dom
        assert rows[i]["dns"]["status"] == "ok"
        assert rows[i]["tcp"][0]["host"] == ips[i]
        assert len(rows[i]["trace"]) == 1
        assert rows[i]["trace"][0]["host"] == ips[i]
    dns_calls = [c for c in d.calls if c[0] == "dns"]
    assert len(dns_calls) == 3


@pytest.mark.asyncio
async def test_run_business_domain_port_probes_dns_failure_sets_agg() -> None:
    ctx = FlowContext(trace_id="t-probe-2")
    script = {
        ("dns", "bad.example"): ToolResponse(
            success=False,
            error_message="timeout",
        ),
    }
    d = _FakeDispatcher(script)
    rows, agg = await run_business_domain_port_probes(
        ctx,
        [BizDomainPortSpec(domain="bad.example", port=80)],
        dns_server=None,
        dispatcher=d,
    )
    assert agg and "bad.example" in agg
    assert rows[0]["dns"]["status"] == "error"
    assert rows[0]["tcp"] == []
    assert rows[0]["trace"] == []
