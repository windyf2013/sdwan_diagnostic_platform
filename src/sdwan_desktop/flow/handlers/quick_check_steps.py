"""一键体检 Flow 步骤处理器：CLI 与 GUI 共用。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.diagnosis import (
    DiagnosisEvidence,
    DiagnosisResult,
    RootCause,
    Severity,
)
from sdwan_desktop.core.types.probe import ProbeResult
from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS, DOMAIN_TO_CATEGORY
from sdwan_desktop.services.analyzer.rule_engine import RuleEngine
from sdwan_desktop.services.collector.windows_collector import WindowsCollector
from sdwan_desktop.services.connectivity import ConnectivityTester
from sdwan_desktop.services.dns_split import DnsSplitTester
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder
from sdwan_desktop.services.reporter.report_delivery_context import build_quick_check_pack

logger = logging.getLogger(__name__)

# 比 Flow 步骤超时略短，便于在内部生成降级结果
_CPE_LINK_INNER_TIMEOUT_S = 110


@dataclass
class QuickCheckHandlerDeps:
    collector: WindowsCollector
    connectivity_tester: ConnectivityTester
    dns_split_tester: DnsSplitTester
    rule_engine: RuleEngine
    report_builder: HtmlReportBuilder


@dataclass
class QuickCheckHandlersParams:
    """控制步骤的终端输出、进度回调与报告路径。"""

    report_output: Optional[Path] = None
    output_format: str = "html"
    progress: Optional[Callable[[int, str], None]] = None
    cancelled: Optional[Callable[[], bool]] = None
    console: bool = True


def _should_cancel(params: QuickCheckHandlersParams) -> bool:
    return bool(params.cancelled and params.cancelled())


def _emit_progress(params: QuickCheckHandlersParams, pct: int, msg: str) -> None:
    if params.progress:
        params.progress(pct, msg)


def _println(params: QuickCheckHandlersParams, msg: str, end: str = "\n", flush: bool = False) -> None:
    if params.console:
        print(msg, end=end, flush=flush)


def build_quick_check_step_handlers(
    deps: QuickCheckHandlerDeps,
    params: QuickCheckHandlersParams,
) -> Dict[str, Callable[..., Awaitable[Any]]]:
    """构建 ``QUICK_CHECK_FLOW`` 的 step_id → handler 映射（不含 ``check_connectivity`` 时可在外部覆盖）。"""

    collector = deps.collector
    connectivity_tester = deps.connectivity_tester
    dns_split_tester = deps.dns_split_tester
    rule_engine = deps.rule_engine
    report_builder = deps.report_builder

    async def step_collect(ctx: FlowContext):
        if _should_cancel(params):
            return None
        _emit_progress(params, 10, "正在采集系统信息...")
        _println(params, "📊 采集系统信息... ", end="", flush=True)
        start = datetime.now()
        snapshot = await collector.collect(ctx)
        ctx.set("system_snapshot", snapshot)
        duration = (datetime.now() - start).total_seconds()
        _println(params, f"✓ ({duration:.1f}s)")
        if params.console and snapshot.adapters:
            for i, adapter in enumerate(snapshot.adapters):
                status_str = "已连接" if adapter.is_connected else "未连接"
                ip_info = f"IP: {adapter.ip_addresses[0]}" if adapter.ip_addresses else "无IP"
                gw_info = f", 网关: {adapter.default_gateway}" if adapter.default_gateway else ""
                print(
                    f"   - 网卡 {i+1}: {adapter.description or adapter.name} "
                    f"[{status_str}, {ip_info}{gw_info}]"
                )
        if params.console:
            primary = snapshot.primary_adapter
            if primary:
                print(
                    "   - [规则引擎视角] 主网卡: "
                    f"{primary.description or primary.name} "
                    f"[is_connected={primary.is_connected}, "
                    f"default_gateway={primary.default_gateway}]"
                )
            else:
                print("   - [规则引擎视角] 主网卡: None")
        return snapshot

    async def step_gateway(ctx: FlowContext):
        if _should_cancel(params):
            return None
        _emit_progress(params, 30, "正在测试网关连通性...")
        _println(params, "🌐 测试网关连通性... ", end="", flush=True)
        start = datetime.now()
        snapshot = ctx.get("system_snapshot")
        gateway_ip = snapshot.ip_config.default_gateway if snapshot and snapshot.ip_config else None
        if not gateway_ip and snapshot and snapshot.primary_adapter:
            gateway_ip = snapshot.primary_adapter.default_gateway
        if not gateway_ip:
            _println(params, "✗ (未找到网关)")
            return None
        result = await connectivity_tester.test_gateway(gateway_ip, ctx)
        ctx.set("gateway_ping_result", result)
        duration = (datetime.now() - start).total_seconds()
        status = "可达" if result.success else "不可达"
        rtt = result.metrics.rtt_avg if result.metrics and result.metrics.rtt_avg is not None else 0
        _println(params, f"✓ ({duration:.1f}s)")
        _println(params, f"   - 网关 {gateway_ip}: {status}, RTT={rtt:.1f}ms")
        return result

    async def step_dns(ctx: FlowContext):
        if _should_cancel(params):
            return None
        _emit_progress(params, 40, "正在测试 DNS 解析...")
        _println(params, "🔬 测试DNS解析... ", end="", flush=True)
        start = datetime.now()
        snapshot = ctx.get("system_snapshot")
        dns_servers = (
            snapshot.ip_config.dns_servers if snapshot and snapshot.ip_config else ["114.114.114.114"]
        )
        results = await connectivity_tester.test_domestic_dns(dns_servers, ctx)
        ctx.set("dns_results", results)
        duration = (datetime.now() - start).total_seconds()
        _println(params, f"✓ ({duration:.1f}s)")
        if params.console:
            for res in results:
                status = "响应正常" if res.success else "超时/失败"
                rtt_str = (
                    f", RTT={res.metrics.rtt_avg:.0f}ms"
                    if res.success and res.metrics and res.metrics.rtt_avg is not None
                    else ""
                )
                host = res.target.host if hasattr(res.target, "host") else res.target
                print(f"   - 国内DNS {host}: {status}{rtt_str}")
        return results

    async def step_internet(ctx: FlowContext):
        if _should_cancel(params):
            return None
        _emit_progress(params, 55, "正在测试互联网连通性...")
        _println(params, "🌐 测试互联网连通性（优化版）... ", end="", flush=True)
        start = datetime.now()
        dns_cache_dict = ctx.get("dns_resolution_cache")
        cache_hit_count = 0
        if dns_cache_dict:
            for domain in DEFAULT_TEST_DOMAINS:
                if domain in dns_cache_dict:
                    cache_hit_count += 1
        result = await connectivity_tester.test_internet_optimized(
            domains=DEFAULT_TEST_DOMAINS,
            ctx=ctx,
            use_cache=True,
        )
        ctx.set("internet_connectivity_result", result)
        duration = (datetime.now() - start).total_seconds()
        cache_info = (
            f" [缓存命中: {cache_hit_count}/{len(DEFAULT_TEST_DOMAINS)}]" if cache_hit_count > 0 else ""
        )
        _println(params, f"✓ ({duration:.1f}s){cache_info}")
        if params.console:
            domestic_ok = sum(1 for t in result.domestic_target_results if t.success)
            international_ok = sum(1 for t in result.international_target_results if t.success)
            domestic_total = len(result.domestic_target_results)
            international_total = len(result.international_target_results)
            print(f"   - 国内成功率: {domestic_ok}/{domestic_total} ({result.domestic_success_rate:.0%})")
            print(
                f"   - 国际成功率: {international_ok}/{international_total} "
                f"({result.international_success_rate:.0%})"
            )
            category_stats: Dict[str, Dict[str, int]] = {}
            for target_result in result.domestic_target_results + result.international_target_results:
                domain = target_result.target.host
                category = DOMAIN_TO_CATEGORY.get(domain, "unknown")
                category_stats.setdefault(category, {"total": 0, "success": 0})
                category_stats[category]["total"] += 1
                if target_result.success:
                    category_stats[category]["success"] += 1
            if category_stats:
                print("   ℹ️  域名分类统计:")
                category_names = {
                    "domestic": "国内核心",
                    "video": "国际视频",
                    "international": "国际核心",
                    "enterprise": "企业办公",
                    "cloud": "云服务",
                    "ecommerce_live": "电商直播",
                }
                for category, stats in category_stats.items():
                    name = category_names.get(category, category)
                    print(f"      - {name}: {stats['success']}/{stats['total']}")
        return result

    async def step_cpe_link_routing(ctx: FlowContext):
        if _should_cancel(params):
            return None
        connectivity_failed = ctx.get("connectivity_failed", False)
        if connectivity_failed:
            _println(params, "⏭️  跳过CPE链路追踪（连通性测试失败）")
            _emit_progress(params, 85, "跳过CPE链路追踪（连通性失败）")
            from sdwan_desktop.services.dns_split import CpeLinkRouteResult

            result = CpeLinkRouteResult(
                total_domains_tested=0,
                domain_results=[],
                detected_links=[],
                link_distribution={},
                is_multi_link=False,
                multi_link_count=0,
                errors=["连通性测试失败，跳过CPE链路追踪"],
            )
            ctx.set("cpe_link_routing_result", result)
            return result
        _emit_progress(params, 85, "正在检测CPE链路分流（精简版，约100-110秒）...")
        _println(params, "🛣️ 检测CPE链路分流（精简版）... ", end="", flush=True)
        start = datetime.now()
        test_domains = DEFAULT_TEST_DOMAINS
        dns_cache_dict = ctx.get("dns_resolution_cache")
        tcping_cache_dict = ctx.get("tcping_results_cache")
        dns_hits = sum(1 for d in test_domains if d in dns_cache_dict) if dns_cache_dict else 0
        tcping_hits = sum(1 for d in test_domains if d in tcping_cache_dict) if tcping_cache_dict else 0
        if params.console and dns_cache_dict:
            print(f"   ℹ️ 检测到DNS解析缓存: {len(dns_cache_dict)}个域名可用")
        try:
            result = await asyncio.wait_for(
                dns_split_tester.test_cpe_link_routing_optimized(
                    domains=test_domains,
                    max_hops=7,
                    cpe_exit_hop=2,
                    ctx=ctx,
                    use_cache=True,
                ),
                timeout=_CPE_LINK_INNER_TIMEOUT_S,
            )
            ctx.set("cpe_link_routing_result", result)
            duration = (datetime.now() - start).total_seconds()
            cache_info = f" [命中DNS:{dns_hits}, TCPing:{tcping_hits}]"
            _println(params, f"✓ ({duration:.1f}s){cache_info}")
            if params.console:
                category_stats: Dict[str, Dict[str, int]] = {}
                for path_result in result.domain_results:
                    domain = path_result.domain
                    category = DOMAIN_TO_CATEGORY.get(domain, "unknown")
                    category_stats.setdefault(category, {"total": 0, "reachable": 0, "unreachable": 0})
                    category_stats[category]["total"] += 1
                    if path_result.link_category == "unreachable":
                        category_stats[category]["unreachable"] += 1
                    else:
                        category_stats[category]["reachable"] += 1
                if category_stats:
                    print("   ℹ️  域名分类统计:")
                    category_names = {
                        "domestic": "国内核心",
                        "international": "国际核心",
                        "enterprise": "企业办公",
                        "cloud": "云服务",
                        "ecommerce_live": "电商直播",
                    }
                    for category, stats in category_stats.items():
                        name = category_names.get(category, category)
                        reachability = f"{stats['reachable']}可达/{stats['unreachable']}不可达"
                        print(f"      - {name}: {reachability}")
                if result.is_multi_link:
                    print(f"   🌐 检测到多链路分流: {result.multi_link_count}条路径")
                    for link_fp, domains_in_link in result.link_distribution.items():
                        print(f"      * [{link_fp}]: {', '.join(domains_in_link)}")
                else:
                    print("   ✅ 所有域名使用相同网络路径")
            return result
        except asyncio.TimeoutError:
            from sdwan_desktop.services.dns_split import CpeLinkRouteResult

            error_result = CpeLinkRouteResult(
                total_domains_tested=0,
                domain_results=[],
                detected_links=[],
                link_distribution={},
                is_multi_link=False,
                multi_link_count=0,
                errors=["CPE链路分流测试超时（110秒限制）"],
            )
            ctx.set("cpe_link_routing_result", error_result)
            duration = (datetime.now() - start).total_seconds()
            _println(params, f"✗ ({duration:.1f}s) - 测试超时")
            return error_result
        except Exception as e:
            from sdwan_desktop.services.dns_split import CpeLinkRouteResult

            error_result = CpeLinkRouteResult(
                total_domains_tested=0,
                domain_results=[],
                detected_links=[],
                link_distribution={},
                is_multi_link=False,
                multi_link_count=0,
                errors=[f"CPE链路分流测试失败: {str(e)}"],
            )
            ctx.set("cpe_link_routing_result", error_result)
            duration = (datetime.now() - start).total_seconds()
            _println(params, f"✗ ({duration:.1f}s) - {e}")
            logger.error("CPE链路分流测试异常: %s", e, extra={"trace_id": ctx.trace_id}, exc_info=True)
            return error_result

    async def step_analyze(ctx: FlowContext):
        if _should_cancel(params):
            return None
        _emit_progress(params, 90, "正在分析诊断结果...")
        _println(params, "📈 分析诊断结果... ", end="", flush=True)
        start = datetime.now()
        from sdwan_desktop.services.analyzer.quick_check_analyzer import QuickCheckAnalyzer

        await QuickCheckAnalyzer.analyze(ctx, rule_engine)
        duration = (datetime.now() - start).total_seconds()
        _println(params, f"✓ ({duration:.1f}s)")
        return ctx.get("rule_results")

    async def step_conclusion(ctx: FlowContext):
        if _should_cancel(params):
            return None
        rule_results = ctx.get("rule_results")
        if not rule_results:
            return None
        root_causes: List[RootCause] = []
        confidence = 1.0
        for rr in rule_results.results:
            if rr.triggered:
                details = rr.details or {}
                evidence_lines = details.get("evidence") or []
                # 规范化：保证 evidence_refs 是 List[str]，让模板可按行渲染
                if not isinstance(evidence_lines, list):
                    evidence_lines = [str(evidence_lines)]
                else:
                    evidence_lines = [str(x) for x in evidence_lines]
                root_causes.append(
                    RootCause(
                        cause_id=rr.rule_id,
                        title=rr.name,
                        description=rr.message,
                        severity=rr.severity,
                        confidence=rr.confidence,
                        evidence_refs=evidence_lines,
                        matched_rules=[rr.rule_id],
                        current_value=details.get("current_value", ""),
                        expected_value=details.get("expected_value", ""),
                        remediation=rr.suggestion or "",
                    )
                )
                confidence = min(confidence, rr.confidence)
        if not root_causes:
            confidence = 1.0
        evidence_connectivity = ctx.get("evidence_connectivity")
        evidences = [evidence_connectivity] if evidence_connectivity else []
        def _sev(cause: RootCause) -> str:
            s = cause.severity
            return s.value if hasattr(s, "value") else str(s)

        crit = sum(1 for c in root_causes if _sev(c) == "critical")
        err = sum(1 for c in root_causes if _sev(c) == "error")
        warn = sum(1 for c in root_causes if _sev(c) == "warning")
        if root_causes:
            summary = f"发现 {len(root_causes)} 项异常"
            if crit or err or warn:
                parts = []
                if crit:
                    parts.append(f"严重 {crit}")
                if err:
                    parts.append(f"错误 {err}")
                if warn:
                    parts.append(f"警告 {warn}")
                summary += f"（{', '.join(parts)}）"
        else:
            summary = "本机网络环境与基础连通性正常"
        diagnosis_result = DiagnosisResult(
            trace_id=ctx.trace_id,
            diagnosis_type="quick_check",
            summary=summary,
            severity=root_causes[0].severity if root_causes else Severity.INFO,
            root_causes=root_causes,
            recommendations=[],
            overall_confidence=confidence,
            timestamp=datetime.now().isoformat(),
            evidences=evidences,
        )
        ctx.set("diagnosis_result", diagnosis_result)
        return diagnosis_result

    async def step_report(ctx: FlowContext):
        if _should_cancel(params):
            return None
        _emit_progress(params, 100, "生成报告...")
        _println(params, "\n📄 生成诊断报告... ", end="", flush=True)
        start = datetime.now()
        result = ctx.get("diagnosis_result")
        cpe_link_result = ctx.get("cpe_link_routing_result")
        if cpe_link_result and result:
            target_evidence = None
            for ev in result.evidences:
                if hasattr(ev, "config_snapshots"):
                    target_evidence = ev
                    break
            if not target_evidence:
                target_evidence = DiagnosisEvidence(
                    step_name="step-cpe-link-routing",
                    description="CPE链路分流测试原始数据",
                )
                result.evidences.append(target_evidence)
            if hasattr(target_evidence, "config_snapshots"):
                target_evidence.config_snapshots["cpe_link_routing_result"] = cpe_link_result

        out_fmt = (ctx.get("output_format") or "html").lower()
        if out_fmt == "json":
            report_path = params.report_output
            if report_path:
                op = Path(report_path)
                json_path = op.with_suffix(".json") if op.suffix.lower() == ".html" else op
            else:
                reports_dir = Path("./reports")
                reports_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                json_path = reports_dir / f"quick_check_{timestamp}.json"
            json_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                if not result:
                    raise RuntimeError("缺少 diagnosis_result，无法生成 JSON")
                pack = build_quick_check_pack(result=result).as_template_dict()
                payload = {
                    "trace_id": result.trace_id,
                    "diagnosis": result.to_json_dict(),
                    "report_pack": pack,
                }
                json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                duration = (datetime.now() - start).total_seconds()
                _println(params, f"✓ ({duration:.1f}s)")
                _println(params, f"   JSON 已保存至: {json_path.absolute()}")
            except Exception as e:
                duration = (datetime.now() - start).total_seconds()
                _println(params, f"✗ ({duration:.1f}s)")
                _println(params, f"   错误: {e}")
                traceback.print_exc()
            return None

        if params.report_output:
            output_path = Path(params.report_output)
        else:
            reports_dir = Path("./reports")
            reports_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = reports_dir / f"quick_check_{timestamp}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not result:
                raise RuntimeError("缺少 diagnosis_result，无法生成 HTML")
            report_builder.build_quick_check_report(result, output_path)
            duration = (datetime.now() - start).total_seconds()
            _println(params, f"✓ ({duration:.1f}s)")
            _println(params, f"   报告已保存至: {output_path.absolute()}")
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            _println(params, f"✗ ({duration:.1f}s)")
            _println(params, f"   错误: {e}")
            traceback.print_exc()
        ctx.set("report_path", str(output_path))
        return output_path

    from sdwan_desktop.flow.handlers.flow_control import check_connectivity

    return {
        "step-collect": step_collect,
        "step-gateway": step_gateway,
        "step-dns": step_dns,
        "step-internet": step_internet,
        "step-connectivity-check": check_connectivity,
        "step-cpe-link-routing": step_cpe_link_routing,
        "step-analyze": step_analyze,
        "step-conclusion": step_conclusion,
        "step-report": step_report,
    }
