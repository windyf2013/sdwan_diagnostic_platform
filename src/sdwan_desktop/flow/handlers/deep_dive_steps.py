"""深度诊断 Flow 步骤处理器：CLI 与 GUI 共用（避免 GUI 再启子进程/onefile 互拉）。"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import sdwan_desktop.tools.implementations.network.dns  # noqa: F401
import sdwan_desktop.tools.implementations.network.tcping  # noqa: F401
import sdwan_desktop.tools.implementations.network.traceroute  # noqa: F401

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity
from sdwan_desktop.flow.definitions.deep_dive import (
    DEEP_DIVE_DEFAULT_BIZ_TARGETS,
    DEEP_DIVE_FLOW,
)
from sdwan_desktop.runtime.engine import FlowRuntime
from sdwan_desktop.services.analyzer.root_cause import RootCauseEngine
from sdwan_desktop.services.collector.cpe_collector import CpeCollector, CpeCollectorConfig
from sdwan_desktop.services.collector.cpe_credentials_loader import (
    default_cpe_credentials_path,
    load_device_credentials_file,
)
from sdwan_desktop.services.collector.cpe_view_credentials_loader import (
    default_cpe_view_credentials_path,
    load_view_credentials_file,
)
from sdwan_desktop.services.collector.windows_collector import WindowsCollector
from sdwan_desktop.services.diagnosis.business_diagnosis import (
    orchestrate_business_domain_port_diagnosis,
)
from sdwan_desktop.services.diagnosis.overlay_policy_flow_evidence import (
    run_overlay_policy_flow_step,
)
from sdwan_desktop.services.probe.business_host_probe import (
    BizDomainPortSpec,
    parse_biz_target_tokens,
)
from sdwan_desktop.services.probe.planner import (
    extract_tunnel_peer_ips_from_cpe_configuration,
    plan_post_topology_probe_commands,
)
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder
from sdwan_desktop.services.topology.pc_topology_input import snapshot_to_topology_input
from sdwan_desktop.services.topology.topology_builder import TopologyBuilder

logger = logging.getLogger(__name__)

DEEP_DIVE_STEP_COUNT = 9

_HEARTBEAT_INTERVAL_S = 30.0


def extract_probe_target_ips(rows: list[dict[str, Any]]) -> list[str]:
    """从业务探测结果提取目标 IP（优先 TCP host，其次 DNS A）。"""
    ips: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tcp_rows = row.get("tcp") if isinstance(row.get("tcp"), list) else []
        for t in tcp_rows:
            if isinstance(t, dict) and t.get("host"):
                ips.append(str(t.get("host")))
        dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
        data = dns.get("data") if isinstance(dns.get("data"), dict) else {}
        for ip in data.get("resolved_ips") or []:
            ips.append(str(ip))
    dedup: list[str] = []
    seen: set[str] = set()
    for ip in ips:
        if ip and ip not in seen:
            seen.add(ip)
            dedup.append(ip)
    return dedup


@dataclass
class DeepDiveHandlerDeps:
    pc_collector: WindowsCollector
    cpe_collector: CpeCollector
    topology_builder: TopologyBuilder
    root_cause_engine: RootCauseEngine
    report_builder: HtmlReportBuilder
    biz_specs: List[BizDomainPortSpec]


@dataclass
class DeepDiveHandlersParams:
    """深度诊断运行参数（CPE 连接 + 报告路径 + 进度回调）。"""

    cpe_host: str
    username: str
    cpe_port: int = 23
    password: Optional[str] = None
    key_file: Optional[str] = None
    protocol: str = "telnet"
    output_path: Path = Path("deep_dive_report.html")
    credentials_file: Optional[Path] = None
    view_credentials_file: Optional[Path] = None
    biz_targets: Tuple[str, ...] = DEEP_DIVE_DEFAULT_BIZ_TARGETS
    biz_dns_server: Optional[str] = None
    no_traceroute: bool = False
    verbose: bool = False
    progress: Optional[Callable[[int, str], None]] = None
    cancelled: Optional[Callable[[], bool]] = None
    console: bool = True


def _should_cancel(params: DeepDiveHandlersParams) -> bool:
    return bool(params.cancelled and params.cancelled())


async def _run_with_heartbeat(
    params: DeepDiveHandlersParams,
    step: int,
    label: str,
    coro: Awaitable[Any],
) -> Any:
    """长耗时步骤内定期刷新进度（仅 GUI 有 progress 回调时生效）。"""
    if not params.progress:
        return await coro

    async def _heartbeat() -> None:
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
            if _should_cancel(params):
                break
            _emit_progress(params, step, label, suffix="进行中…")

    task = asyncio.create_task(_heartbeat())
    try:
        return await coro
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def _emit_progress(params: DeepDiveHandlersParams, step: int, label: str, *, suffix: str = "") -> None:
    pct = max(1, min(99, int(100 * step / DEEP_DIVE_STEP_COUNT)))
    text = f"[{step}/{DEEP_DIVE_STEP_COUNT}] {label}"
    if suffix:
        text = f"{text} {suffix}"
    if params.progress:
        params.progress(pct, text)
    if params.console:
        if suffix:
            print(f"[{step}/{DEEP_DIVE_STEP_COUNT}] {label}... {suffix}", flush=True)
        else:
            print(f"[{step}/{DEEP_DIVE_STEP_COUNT}] {label}... ", end="", flush=True)


def _println(params: DeepDiveHandlersParams, msg: str, *, end: str = "\n", flush: bool = False) -> None:
    if params.console:
        print(msg, end=end, flush=flush)


def build_deep_dive_step_handlers(
    deps: DeepDiveHandlerDeps,
    params: DeepDiveHandlersParams,
) -> Dict[str, Callable[..., Awaitable[Any]]]:
    """构建 ``DEEP_DIVE_FLOW`` 的 step_id → handler 映射。"""
    cpe_host = params.cpe_host
    biz_specs = deps.biz_specs
    biz_dns_server = params.biz_dns_server
    no_traceroute = params.no_traceroute
    output_path = params.output_path

    pc_collector = deps.pc_collector
    cpe_collector = deps.cpe_collector
    topology_builder = deps.topology_builder
    root_cause_engine = deps.root_cause_engine
    report_builder = deps.report_builder

    async def step_pc_collect(ctx: FlowContext) -> Any:
        if _should_cancel(params):
            raise asyncio.CancelledError("用户取消")
        _emit_progress(params, 1, "采集 PC 端系统信息")
        snapshot = await pc_collector.collect(ctx)
        ctx.set("pc_snapshot", snapshot)
        if params.console and not params.progress:
            print("OK")
        elif params.progress:
            _emit_progress(params, 1, "采集 PC 端系统信息", suffix="OK")
        return snapshot

    async def step_cpe_connect(ctx: FlowContext) -> bool:
        if _should_cancel(params):
            raise asyncio.CancelledError("用户取消")
        _emit_progress(params, 2, "连接 CPE 设备")
        try:
            is_valid = await cpe_collector.validate(ctx)
            if not is_valid:
                raise RuntimeError("CPE 配置验证失败")
            await cpe_collector._connect()
            await cpe_collector._disconnect()
            if params.console and not params.progress:
                print("OK")
            elif params.progress:
                _emit_progress(params, 2, "连接 CPE 设备", suffix="OK")
        except Exception as exc:
            _emit_progress(params, 2, "连接 CPE 设备", suffix=f"FAIL ({exc})")
            raise
        return True

    async def step_cpe_collect(ctx: FlowContext) -> Any:
        if _should_cancel(params):
            raise asyncio.CancelledError("用户取消")
        _emit_progress(params, 3, "采集 CPE 配置信息")
        result = await cpe_collector.collect(ctx)
        ctx.set("cpe_result", result)
        if result.success:
            dt = result.data.get("device_type") if isinstance(result.data, dict) else None
            if dt:
                ctx.set("cpe_device_type", dt)
            suffix = "OK"
            if params.console:
                print(suffix)
                artifact_paths = (
                    result.data.get("artifact_paths", {}) if isinstance(result.data, dict) else {}
                )
                if artifact_paths:
                    _println(params, "    原始与解析文件已保存:")
                    _println(params, f"    - RAW TXT : {artifact_paths.get('raw_text', '')}")
                    _println(params, f"    - RAW JSON: {artifact_paths.get('raw_json', '')}")
                    _println(params, f"    - PARSED  : {artifact_paths.get('parsed_json', '')}")
            _emit_progress(params, 3, "采集 CPE 配置信息", suffix=suffix)
        else:
            suffix = f"FAIL ({result.error_message})"
            if params.console:
                print(suffix)
            _emit_progress(params, 3, "采集 CPE 配置信息", suffix=suffix)
        return result

    async def step_topology_build(ctx: FlowContext) -> Any:
        if _should_cancel(params):
            raise asyncio.CancelledError("用户取消")
        _emit_progress(params, 4, "构建网络拓扑")
        pc_data = snapshot_to_topology_input(ctx.get("pc_snapshot"))
        cpe_result = ctx.get("cpe_result")
        topology = topology_builder.build(pc_data, cpe_result, cpe_mgmt_ip=str(cpe_host))
        ctx.set("topology", topology)
        if params.console and not params.progress:
            print("OK")
        else:
            _emit_progress(params, 4, "构建网络拓扑", suffix="OK")
        return topology

    def _probe_device_type(ctx: FlowContext) -> str:
        cpe_result = ctx.get("cpe_result")
        dt = ctx.get("cpe_device_type")
        if cpe_result and cpe_result.success and isinstance(cpe_result.data, dict):
            dt = dt or cpe_result.data.get("device_type")
        return str(dt or "generic")

    async def step_biz_probe(ctx: FlowContext) -> dict[str, Any]:
        if _should_cancel(params):
            raise asyncio.CancelledError("用户取消")
        _emit_progress(params, 5, "PC 侧业务探测")
        data: dict[str, Any] = {"device_type": _probe_device_type(ctx)}
        biz_agg: Optional[str] = None
        if not biz_specs:
            partial = {"status": "skipped", "data": data, "error": None, "biz_agg": None}
            ctx.set("targeted_probe_pc", partial)
            if params.console and not params.progress:
                print("SKIP")
            else:
                _emit_progress(params, 5, "PC 侧业务探测", suffix="SKIP")
            return partial

        async def _run_biz() -> Any:
            return await orchestrate_business_domain_port_diagnosis(
                ctx,
                biz_specs,
                biz_dns_server,
                None,
                compare_system_dns=bool(biz_dns_server),
                enable_traceroute=not no_traceroute,
            )

        biz_outcome = await _run_with_heartbeat(
            params, 5, "PC 侧业务探测", _run_biz()
        )
        data["business_probes"] = biz_outcome.business_probes
        biz_target_ips = extract_probe_target_ips(list(biz_outcome.business_probes))
        if biz_target_ips:
            data["biz_target_ips"] = biz_target_ips
        biz_agg = biz_outcome.aggregate_error
        partial = {
            "status": "partial" if biz_agg else "ok",
            "data": data,
            "error": biz_agg,
            "biz_agg": biz_agg,
        }
        ctx.set("targeted_probe_pc", partial)
        suffix = "OK" if not biz_agg else "PARTIAL"
        if params.console and not params.progress:
            print(suffix)
        else:
            _emit_progress(params, 5, "PC 侧业务探测", suffix=suffix)
        return partial

    async def step_cpe_post_probe(ctx: FlowContext) -> dict[str, Any]:
        if _should_cancel(params):
            raise asyncio.CancelledError("用户取消")
        _emit_progress(params, 6, "CPE 拓扑后补采")
        cpe_result = ctx.get("cpe_result")
        pc_partial = ctx.get("targeted_probe_pc")
        if not isinstance(pc_partial, dict):
            pc_partial = {"status": "skipped", "data": {}, "error": None, "biz_agg": None}
        data: dict[str, Any] = dict(pc_partial.get("data") or {})
        data["device_type"] = _probe_device_type(ctx)
        biz_agg = pc_partial.get("biz_agg")
        cpe_error: Optional[str] = None

        biz_target_ips = list(data.get("biz_target_ips") or [])
        cfg = (
            cpe_result.data.get("cpe_configuration")
            if cpe_result and cpe_result.success and isinstance(cpe_result.data, dict)
            else None
        )
        tunnel_peer_ips = extract_tunnel_peer_ips_from_cpe_configuration(cfg)
        if tunnel_peer_ips:
            data["tunnel_peer_ips"] = tunnel_peer_ips
        cmds = plan_post_topology_probe_commands(
            data.get("device_type") or "generic",
            biz_target_ips=biz_target_ips,
            tunnel_peer_ips=tunnel_peer_ips or None,
        )
        run_cpe = bool(cpe_result and cpe_result.success and cmds)
        run_biz = bool(biz_specs)

        if not run_cpe and not run_biz:
            envelope = {"status": "skipped", "data": data, "error": None}
            ctx.set("targeted_probe", envelope)
            if params.console and not params.progress:
                print("SKIP")
            else:
                _emit_progress(params, 6, "CPE 拓扑后补采", suffix="SKIP")
            return envelope

        if run_cpe:

            async def _run_cpe() -> Any:
                return await cpe_collector.run_probe_commands(ctx, cmds)

            try:
                pr = await _run_with_heartbeat(
                    params, 6, "CPE 拓扑后补采", _run_cpe()
                )
                raw = dict((pr.data or {}).get("raw_outputs") or {})
                data["raw_outputs"] = raw
                if isinstance(pr.data, dict) and pr.data.get("device_type"):
                    data["device_type"] = pr.data.get("device_type")
                if not pr.success:
                    cpe_error = pr.error_message or "CPE 拓扑后探测失败"
            except Exception as exc:
                logger.warning("CPE 拓扑后探测异常: %s", exc, exc_info=True)
                cpe_error = str(exc)
                data.setdefault("raw_outputs", {})
        elif cpe_result and cpe_result.success and not cmds:
            data["reason"] = "no_probe_for_device_type"

        err_parts = [x for x in (cpe_error, biz_agg) if x]
        envelope_error = "; ".join(err_parts) if err_parts else None
        status = "partial" if envelope_error else "ok"
        envelope = {"status": status, "data": data, "error": envelope_error}
        ctx.set("targeted_probe", envelope)
        suffix = "OK" if status == "ok" else status.upper()
        if params.console and not params.progress:
            print(suffix)
        else:
            _emit_progress(params, 6, "CPE 拓扑后补采", suffix=suffix)
        return envelope

    async def step_overlay_policy_flow(ctx: FlowContext) -> Any:
        if _should_cancel(params):
            raise asyncio.CancelledError("用户取消")
        _emit_progress(params, 7, "Overlay 与策略分流证据链")
        await run_overlay_policy_flow_step(ctx)
        if params.console and not params.progress:
            print("OK")
        else:
            _emit_progress(params, 7, "Overlay 与策略分流证据链", suffix="OK")
        return ctx.get("overlay_policy_flow")

    async def step_root_cause(ctx: FlowContext) -> Any:
        if _should_cancel(params):
            raise asyncio.CancelledError("用户取消")
        _emit_progress(params, 8, "执行根因分析")
        topology = ctx.get("topology")
        cpe_result = ctx.get("cpe_result")
        pc_data = ctx.get("pc_snapshot")
        pc_data_dict = (
            snapshot_to_topology_input(pc_data) if pc_data is not None else {}
        )
        causes = root_cause_engine.analyze(
            topology,
            cpe_result,
            pc_data_dict,
            targeted_probe=ctx.get("targeted_probe"),
            trace_id=ctx.trace_id,
            pc_snapshot=ctx.get("pc_snapshot"),
            overlay_policy_flow=ctx.get("overlay_policy_flow"),
        )
        ctx.set("root_causes", causes)
        suffix = f"OK (发现 {len(causes)} 个潜在问题)"
        if params.console and not params.progress:
            print(suffix)
        else:
            _emit_progress(params, 8, "执行根因分析", suffix=suffix)
        return causes

    async def step_report_gen(ctx: FlowContext) -> Path:
        if _should_cancel(params):
            raise asyncio.CancelledError("用户取消")
        _emit_progress(params, 9, "生成专业报告")
        causes = ctx.get("root_causes", [])
        topology = ctx.get("topology")
        cpe_result = ctx.get("cpe_result")

        if any(c.severity == Severity.CRITICAL for c in causes):
            sev = Severity.CRITICAL
        elif any(c.severity == Severity.ERROR for c in causes):
            sev = Severity.ERROR
        elif any(c.severity == Severity.WARNING for c in causes):
            sev = Severity.WARNING
        else:
            sev = Severity.INFO

        diagnosis_result = DiagnosisResult(
            trace_id=ctx.trace_id,
            diagnosis_type="deep_dive",
            root_causes=causes,
            severity=sev,
            summary=f"深度诊断完成，共识别出 {len(causes)} 个问题。",
            overall_confidence=0.9,
        )

        out_path = output_path
        try:
            from sdwan_desktop.interface.cli.commands.deep_dive import (
                _enrich_topology_report_dict,
            )
            from sdwan_desktop.interface.cli.commands import business_diagnose as biz_cmd
            from sdwan_desktop.services.reporter.deep_dive_report_presentation import (
                build_deep_dive_report_outcome,
            )
            from sdwan_desktop.services.reporter.joint_commercial_delivery import (
                build_commercial_delivery_payload,
            )

            topo_dict = topology.to_dict()
            _enrich_topology_report_dict(topo_dict)

            report_hints: list[str] = []
            report_hints.extend(topo_dict.get("topology_notes") or [])

            if (
                cpe_result
                and cpe_result.success
                and isinstance(cpe_result.data, dict)
                and cpe_result.data.get("cpe_configuration") is not None
            ):
                cfg = cpe_result.data["cpe_configuration"]
                wan = cfg.wan_interfaces
                report_hints.extend(
                    [
                        f"CPE 主机名: {cfg.hostname}",
                        f"设备: {cfg.model} · 软件 {cfg.version}",
                        f"VPN 隧道（解析）: {len(cfg.vpn_tunnels)} 条",
                    ]
                )
                if wan:
                    report_hints.append(
                        "WAN: "
                        + ", ".join(
                            f"{i.name} → {i.ip_address or '—'}" for i in wan[:6]
                        )
                    )

            if report_hints:
                topo_dict["hints"] = report_hints

            tp = ctx.get("targeted_probe")
            if isinstance(tp, dict) and tp:
                topo_dict["targeted_probe"] = tp
            opf = ctx.get("overlay_policy_flow")
            if isinstance(opf, dict) and opf.get("data"):
                topo_dict["overlay_policy_flow"] = opf
            topo_dict["pc_snapshot_included"] = ctx.get("pc_snapshot") is not None

            cfg = None
            if (
                cpe_result
                and cpe_result.success
                and isinstance(cpe_result.data, dict)
            ):
                cfg = cpe_result.data.get("cpe_configuration")

            biz_cmd._annotate_problem_nodes(
                topo_dict,
                causes,
                tp if isinstance(tp, dict) else None,
                cpe_configuration=cfg,
            )

            delivery = build_commercial_delivery_payload(
                trace_id=ctx.trace_id,
                diagnosis=diagnosis_result,
                topology_dict=topo_dict,
                targeted_probe=tp if isinstance(tp, dict) else None,
            )
            if delivery is not None:
                topo_dict["commercial_delivery"] = delivery.as_template_dict()

            topo_dict["report_deep_dive_outcome"] = build_deep_dive_report_outcome(
                diagnosis=diagnosis_result,
                topology_dict=topo_dict,
                targeted_probe=tp if isinstance(tp, dict) else None,
                commercial_delivery=topo_dict.get("commercial_delivery"),
                cpe_configuration=cfg,
            )

            report_builder.build_deep_dive_report(diagnosis_result, topo_dict, out_path)
            ctx.set("report_path", str(out_path))
            if params.console:
                if not params.progress:
                    print("OK")
                _println(params, f"\n报告已保存: {out_path}")
            if params.progress:
                params.progress(100, f"报告已保存: {out_path.name}")
        except Exception as exc:
            if params.console:
                print(f"FAIL ({exc})")
            logger.error("报告生成失败: %s", exc, exc_info=True)
            raise

        return out_path

    return {
        "step-pc-collect": step_pc_collect,
        "step-cpe-connect": step_cpe_connect,
        "step-cpe-collect": step_cpe_collect,
        "step-topology-build": step_topology_build,
        "step-biz-probe": step_biz_probe,
        "step-cpe-post-probe": step_cpe_post_probe,
        "step-overlay-policy-flow": step_overlay_policy_flow,
        "step-root-cause": step_root_cause,
        "step-report-gen": step_report_gen,
    }


def _resolve_credentials(params: DeepDiveHandlersParams) -> tuple[Optional[str], Optional[str]]:
    cred_path = params.credentials_file or default_cpe_credentials_path()
    file_creds = load_device_credentials_file(cred_path, params.cpe_host)
    login_password = params.password if params.password else file_creds.get("password")
    testnode_password = file_creds.get("testnode_password")
    return login_password, testnode_password


def _configure_flow_logging(verbose: bool) -> None:
    """配置 Flow 日志；GUI 无控制台时避免向 ``None`` 的 stderr ``flush``。"""
    import sys

    from sdwan_desktop.core.subprocess_platform import ensure_gui_stdio

    ensure_gui_stdio()
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    if sys.stderr is not None:
        logging.basicConfig(level=level, format=fmt)
    else:
        root.setLevel(level)


async def run_deep_dive_flow(params: DeepDiveHandlersParams) -> Path:
    """执行深度诊断 Flow；GUI/CLI 统一入口。"""
    _configure_flow_logging(params.verbose)

    if params.console:
        _println(params, "SD-WAN 深度诊断 v1.0.0")
    trace_id = str(uuid.uuid4())
    if params.console:
        _println(params, f"Trace ID: {trace_id}")
        _println(
            params,
            f"Target CPE: {params.cpe_host}:{params.cpe_port} ({params.username}) "
            f"via {params.protocol.upper()}",
        )
        _println(params, "")

    try:
        biz_specs: List[BizDomainPortSpec] = parse_biz_target_tokens(params.biz_targets)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    login_password, testnode_password = _resolve_credentials(params)
    view_cred_path = params.view_credentials_file or default_cpe_view_credentials_path()
    view_presets = load_view_credentials_file(view_cred_path)

    cpe_config = CpeCollectorConfig(
        host=params.cpe_host,
        port=params.cpe_port,
        username=params.username,
        password=login_password,
        private_key=params.key_file,
        protocol=params.protocol,
        testnode_password=testnode_password,
        preset_view_passwords=view_presets,
    )

    deps = DeepDiveHandlerDeps(
        pc_collector=WindowsCollector(),
        cpe_collector=CpeCollector(config=cpe_config),
        topology_builder=TopologyBuilder(),
        root_cause_engine=RootCauseEngine(),
        report_builder=HtmlReportBuilder(),
        biz_specs=biz_specs,
    )

    ctx = FlowContext(trace_id=trace_id)
    handlers = build_deep_dive_step_handlers(deps, params)
    runtime = FlowRuntime()
    await runtime.execute_flow(DEEP_DIVE_FLOW, ctx, handlers)

    report_path = ctx.get("report_path")
    if report_path:
        return Path(report_path)
    return params.output_path


def handler_params_from_gui(
    gui_params: Any,
    output_path: Path,
    *,
    progress: Optional[Callable[[int, str], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
    console: bool = False,
) -> DeepDiveHandlersParams:
    """由 ``DeepDiveGuiRunParams`` 构造 Flow 运行参数。"""
    cred = Path(gui_params.credentials_file) if gui_params.credentials_file else None
    view = (
        Path(gui_params.view_credentials_file)
        if gui_params.view_credentials_file
        else None
    )
    return DeepDiveHandlersParams(
        cpe_host=gui_params.cpe_host,
        username=gui_params.username,
        cpe_port=gui_params.cpe_port,
        password=gui_params.password,
        key_file=gui_params.key_file,
        protocol=gui_params.protocol,
        output_path=output_path,
        credentials_file=cred,
        view_credentials_file=view,
        biz_targets=gui_params.biz_targets,
        biz_dns_server=gui_params.biz_dns_server,
        no_traceroute=gui_params.no_traceroute,
        verbose=gui_params.verbose,
        progress=progress,
        cancelled=cancelled,
        console=console,
    )
