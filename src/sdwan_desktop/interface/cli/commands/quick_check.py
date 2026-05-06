"""
一键体检 CLI 命令
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
from sdwan_desktop.runtime.engine import FlowRuntime
from sdwan_desktop.services.collector.windows_collector import WindowsCollector
from sdwan_desktop.services.connectivity import ConnectivityTester
from sdwan_desktop.services.dns_split import DnsSplitTester
from sdwan_desktop.services.analyzer.rule_engine import RuleEngine
from sdwan_desktop.services.analyzer.rules import (
    GATEWAY_RULES, DNS_RULES, SYSTEM_RULES, CONNECTIVITY_RULES
)
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder
from sdwan_desktop.interface.cli.formatters import (
    format_diagnosis_summary, 
    format_recommendations,
    colorize
)
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity

logger = logging.getLogger(__name__)


@click.command()
@click.option('--output', '-o', default=None, help='报告输出路径 (默认: ./reports/quick_check_<timestamp>.html)')
@click.option('--format', '-f', 'fmt', default='html', type=click.Choice(['html', 'json']), help='输出格式 (默认: html)')
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
@click.option('--no-parallel', is_flag=True, help='禁用并行执行')
def quick_check(output: Optional[str], fmt: str, verbose: bool, no_parallel: bool):
    """执行 SD-WAN 一键体检"""
    
    # 设置日志
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 确保工具注册
    from sdwan_desktop.tools.implementations.system.windows import WindowsSystemTool
    from sdwan_desktop.tools.implementations.network.dns import DnsTool
    from sdwan_desktop.tools.implementations.network.tcping import TcpPortTool
    from sdwan_desktop.tools.implementations.network.ping import PingTool
    from sdwan_desktop.tools.implementations.network.traceroute import TraceRouteTool

    print("🔍 SD-WAN 一键体检 v1.0.0")
    
    # 创建上下文
    import uuid
    trace_id = str(uuid.uuid4())
    print(f"Trace ID: {trace_id}")
    print("")
    
    ctx = FlowContext(trace_id=trace_id)
    
    # 初始化服务
    collector = WindowsCollector()
    connectivity_tester = ConnectivityTester()
    dns_split_tester = DnsSplitTester()
    
    # 初始化规则引擎
    rule_engine = RuleEngine()
    rule_engine.register_rules(GATEWAY_RULES)
    rule_engine.register_rules(DNS_RULES)
    rule_engine.register_rules(SYSTEM_RULES)
    rule_engine.register_rules(CONNECTIVITY_RULES)
    
    # 初始化报告生成器
    report_builder = HtmlReportBuilder()
    
    # 定义步骤处理器映射
    # 注意：这里的 handler 签名需要适配 FlowRuntime 的调用方式
    # FlowRuntime 期望 handler(ctx=ctx, ...)
    
    async def step_collect(ctx: FlowContext):
        print("📊 采集系统信息... ", end="", flush=True)
        start = datetime.now()
        snapshot = await collector.collect(ctx)
        ctx.set("system_snapshot", snapshot)
        duration = (datetime.now() - start).total_seconds()
        print(f"✓ ({duration:.1f}s)")
        
        # 打印详细网卡状态，用于诊断摘要对比
        if snapshot.adapters:
            for i, adapter in enumerate(snapshot.adapters):
                status_str = "已连接" if adapter.is_connected else "未连接"
                ip_info = f"IP: {adapter.ip_addresses[0]}" if adapter.ip_addresses else "无IP"
                gw_info = f", 网关: {adapter.default_gateway}" if adapter.default_gateway else ""
                print(f"   - 网卡 {i+1}: {adapter.description or adapter.name} [{status_str}, {ip_info}{gw_info}]")
        
        # 显式打印 primary_adapter 的判断结果
        primary = snapshot.primary_adapter
        if primary:
            print(f"   - [规则引擎视角] 主网卡: {primary.description or primary.name} [is_connected={primary.is_connected}, default_gateway={primary.default_gateway}]")
        else:
            print(f"   - [规则引擎视角] 主网卡: None")
            
        return snapshot

    async def step_gateway(ctx: FlowContext):
        print("🌐 测试网关连通性... ", end="", flush=True)
        start = datetime.now()
        snapshot = ctx.get("system_snapshot")
        gateway_ip = snapshot.ip_config.default_gateway if snapshot and snapshot.ip_config else None
        
        # 如果 ip_config 中没有，尝试从 primary_adapter 获取
        if not gateway_ip and snapshot and snapshot.primary_adapter:
            gateway_ip = snapshot.primary_adapter.default_gateway
            
        if not gateway_ip:
            print("✗ (未找到网关)")
            return None
            
        result = await connectivity_tester.test_gateway(gateway_ip, ctx)
        ctx.set("gateway_ping_result", result)
        duration = (datetime.now() - start).total_seconds()
        status = "可达" if result.success else "不可达"
        rtt = result.metrics.rtt_avg if result.metrics and result.metrics.rtt_avg is not None else 0
        print(f"✓ ({duration:.1f}s)")
        print(f"   - 网关 {gateway_ip}: {status}, RTT={rtt:.1f}ms")
        return result

    async def step_dns(ctx: FlowContext):
        print("🔬 测试DNS解析... ", end="", flush=True)
        start = datetime.now()
        snapshot = ctx.get("system_snapshot")
        dns_servers = snapshot.ip_config.dns_servers if snapshot and snapshot.ip_config else ["114.114.114.114"]
        
        # 使用 ConnectivityTester 的通用探测方法，或者手动构造 DNS 探测
        # 这里为了简化，我们直接调用 test_domestic_dns，但需要传入服务器列表
        results = await connectivity_tester.test_domestic_dns(dns_servers, ctx)
        ctx.set("dns_results", results)
        duration = (datetime.now() - start).total_seconds()
        print(f"✓ ({duration:.1f}s)")
        for res in results:
            status = "响应正常" if res.success else "超时/失败"
            rtt_str = f", RTT={res.metrics.rtt_avg:.0f}ms" if res.success and res.metrics and res.metrics.rtt_avg is not None else ""
            print(f"   - 国内DNS {res.target}: {status}{rtt_str}")
        return results

    async def step_internet(ctx: FlowContext):
        print("🌍 测试互联网连通性... ", end="", flush=True)
        start = datetime.now()
        
        # 方案更新：对 baidu/google/youtube/tiktok 进行连通性测试
        domestic_targets = [
            {"host": "www.baidu.com", "type": "http"},
        ]
        international_targets = [
            {"host": "www.google.com", "type": "http"},
            {"host": "www.youtube.com", "type": "http"},
            {"host": "www.tiktok.com", "type": "http"},
        ]
        
        domestic_res = await connectivity_tester.test_domestic_targets(domestic_targets, ctx)
        international_res = await connectivity_tester.test_international_targets(international_targets, ctx)
        
        ctx.set("domestic_connectivity", domestic_res)
        ctx.set("international_connectivity", international_res)
        
        duration = (datetime.now() - start).total_seconds()
        print(f"✓ ({duration:.1f}s)")
        
        dom_success = sum(1 for r in domestic_res if r.success)
        dom_total = len(domestic_res)
        int_success = sum(1 for r in international_res if r.success)
        int_total = len(international_res)
        
        print(f"   - 国内目标: {dom_success}/{dom_total} 成功")
        for r in domestic_res:
            status = "可达" if r.success else "不可达"
            loss_str = f", 丢包={r.metrics.loss_rate*100:.1f}%" if r.metrics and r.metrics.loss_rate is not None else ""
            print(f"     {r.target.host}: {status}{loss_str}")
            
        print(f"   - 国际目标: {int_success}/{int_total} 成功")
        for r in international_res:
            status = "可达" if r.success else "不可达"
            loss_str = f", 丢包={r.metrics.loss_rate*100:.1f}%" if r.metrics and r.metrics.loss_rate is not None else ""
            print(f"     {r.target.host}: {status}{loss_str}")
        
        return {"domestic": domestic_res, "international": international_res}

    async def step_dns_split(ctx: FlowContext):
        print("🔎 测试DNS解析差异... ", end="", flush=True)
        start = datetime.now()
        
        # 方案更新：使用系统默认 DNS，对 baidu/google/youtube/tiktok 进行请求测试
        snapshot = ctx.get("system_snapshot")
        system_dns_servers = snapshot.ip_config.dns_servers if snapshot and snapshot.ip_config else []
        
        # 如果系统没有配置 DNS，则回退到公共 DNS
        if not system_dns_servers:
            system_dns_servers = ["114.114.114.114"]
            
        domains = ["www.baidu.com", "www.google.com", "www.youtube.com", "www.tiktok.com"]
        
        # 逻辑修正：由于当前环境无法模拟"不同出口"，我们采用对比"系统 DNS"与"国际公共 DNS (8.8.8.8)"的策略
        # 这能反映出在当前网络路径下，本地 DNS 与国际权威/公共 DNS 的解析差异
        result = await dns_split_tester.test_all_domains(
            domains=domains,
            domestic_dns=system_dns_servers,
            international_dns=["8.8.8.8"], 
            ctx=ctx
        )
        
        ctx.set("dns_split_result", result)
        duration = (datetime.now() - start).total_seconds()
        print(f"✓ ({duration:.1f}s)")
        
        for dr in result.domain_results:
            status = "存在分流差异" if dr.is_split else "解析一致"
            print(f"   - {dr.domain}: {status}")
            
        return result

    async def step_cpe_link_routing(ctx: FlowContext):
        print("🛣️ 检测CPE链路分流... ", end="", flush=True)
        start = datetime.now()
        
        # 方案更新：对 baidu/google/youtube/tiktok 进行路径追踪测试
        test_domains = [
            "www.baidu.com",      # 国内搜索
            "www.google.com",     # 国际搜索
            "www.youtube.com",    # 国际视频
            "www.tiktok.com",     # 国际短视频
        ]
        
        result = await dns_split_tester.test_cpe_link_routing(
            domains=test_domains,
            max_hops=6,  # 优化：仅追踪6跳，大幅缩短执行时间
            cpe_exit_hop=2,
            ctx=ctx
        )
        
        ctx.set("cpe_link_routing_result", result)
        duration = (datetime.now() - start).total_seconds()
        print(f"✓ ({duration:.1f}s)")
        
        if result.is_multi_link:
            print(f"   - 检测到多链路分流: {result.multi_link_count}条链路")
            for link_fp, domains_in_link in result.link_distribution.items():
                print(f"     * 链路 [{link_fp}]: {', '.join(domains_in_link)}")
        else:
            print(f"   - 所有域名使用相同链路")
            
        return result

    async def step_analyze(ctx: FlowContext):
        print("📈 分析诊断结果... ", end="", flush=True)
        start = datetime.now()
        
        from sdwan_desktop.services.analyzer.rule_context import QuickCheckContext
        
        system_snapshot = ctx.get("system_snapshot")
        gateway_ping = ctx.get("gateway_ping_result")
        dns_results = ctx.get("dns_results")
        domestic_conn = ctx.get("domestic_connectivity")
        international_conn = ctx.get("international_connectivity")
        dns_split = ctx.get("dns_split_result")
        
        # 构造 QuickCheckContext 需要的聚合对象
        from sdwan_desktop.services.connectivity import ConnectivityTestResult, ProbeResult
        
        # 确保 dns_results 是 ProbeResult 列表，而不是其他格式
        clean_dns_results = []
        if dns_results:
            for r in dns_results:
                if isinstance(r, ProbeResult):
                    clean_dns_results.append(r)
        
        conn_result = ConnectivityTestResult(
            gateway_ping=gateway_ping,
            domestic_dns_results=clean_dns_results,
            international_dns_results=[],
            domestic_target_results=domestic_conn or [],
            international_target_results=international_conn or []
        )
        
        qc_ctx = QuickCheckContext(
            system_info=system_snapshot,
            connectivity=conn_result,
            dns_split=dns_split
        )
        
        rule_results = rule_engine.evaluate(qc_ctx)
        ctx.set("rule_results", rule_results)
        
        # 将原始探测数据存入证据，供报告生成器使用
        from sdwan_desktop.core.types.diagnosis import DiagnosisEvidence
        all_probes = []
        if gateway_ping: all_probes.append(gateway_ping)
        all_probes.extend(clean_dns_results)
        if domestic_conn: all_probes.extend(domestic_conn)
        if international_conn: all_probes.extend(international_conn)
        
        evidence = DiagnosisEvidence(
            step_name="connectivity_test",
            description="连通性测试原始探测数据",
            probe_results=all_probes,
            config_snapshots={"system_snapshot": system_snapshot} # 增加系统快照
        )
        ctx.set("evidence_connectivity", evidence)
        
        duration = (datetime.now() - start).total_seconds()
        print(f"✓ ({duration:.1f}s)")
        
        return rule_results

    async def step_conclusion(ctx: FlowContext):
        # 生成诊断结论
        rule_results = ctx.get("rule_results")
        if not rule_results:
            return
            
        root_causes = []
        recommendations = []
        confidence = 1.0
        
        # rule_results 是一个 RuleEvaluationResult 对象，包含 results 列表
        for rr in rule_results.results:
            if rr.triggered:
                from sdwan_desktop.core.types.diagnosis import RootCause, Recommendation
                root_causes.append(RootCause(
                    cause_id=rr.rule_id,
                    title=rr.name,
                    description=rr.message,
                    severity=rr.severity,
                    confidence=rr.confidence,
                    evidence_refs=[],
                    matched_rules=[rr.rule_id]
                ))
                if rr.suggestion:
                    recommendations.append(Recommendation(
                        action=rr.suggestion,
                        priority=1 if rr.severity in [Severity.CRITICAL, Severity.ERROR] else 2,
                        expected_outcome=rr.message
                    ))

                confidence = min(confidence, rr.confidence)
        
        # 如果没有触发任何规则，说明网络正常
        if not root_causes:
            confidence = 1.0
                
        diagnosis_result = DiagnosisResult(
            trace_id=ctx.trace_id,
            root_causes=root_causes,
            recommendations=recommendations,
            overall_confidence=confidence,
            timestamp=datetime.now().isoformat(),
            evidences=[ctx.get("evidence_connectivity")] # 关联证据
        )
        ctx.set("diagnosis_result", diagnosis_result)
        return diagnosis_result

    async def step_report(ctx: FlowContext):
        print("\n📄 生成诊断报告... ", end="", flush=True)
        start = datetime.now()
        
        result = ctx.get("diagnosis_result")
        
        # 显式将 DNS 分流结果存入证据的 config_snapshots，确保 HTML 构建器能抓取到
        dns_split_result = ctx.get("dns_split_result")
        if dns_split_result and result:
            # 查找或创建对应的 Evidence
            target_evidence = None
            for ev in result.evidences:
                if hasattr(ev, 'config_snapshots'):
                    target_evidence = ev
                    break
            
            if not target_evidence:
                from sdwan_desktop.core.types.diagnosis import DiagnosisEvidence
                target_evidence = DiagnosisEvidence(
                    step_name="step-dns-split",
                    description="DNS分流测试原始数据"
                )
                result.evidences.append(target_evidence)
            
            if hasattr(target_evidence, 'config_snapshots'):
                target_evidence.config_snapshots["dns_split_result"] = dns_split_result

        # 新增：将 CPE 链路分流结果存入证据
        cpe_link_result = ctx.get("cpe_link_routing_result")
        if cpe_link_result and result:
            target_evidence = None
            for ev in result.evidences:
                if hasattr(ev, 'config_snapshots'):
                    target_evidence = ev
                    break
            
            if not target_evidence:
                from sdwan_desktop.core.types.diagnosis import DiagnosisEvidence
                target_evidence = DiagnosisEvidence(
                    step_name="step-cpe-link-routing",
                    description="CPE链路分流检测原始数据"
                )
                result.evidences.append(target_evidence)
            
            if hasattr(target_evidence, 'config_snapshots'):
                target_evidence.config_snapshots["cpe_link_routing_result"] = cpe_link_result

        output_path = output or f"./reports/quick_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        report_builder.build_quick_check_report(result, Path(output_path))
        duration = (datetime.now() - start).total_seconds()
        print(f"✓ ({duration:.1f}s)")
        print(f"   报告已保存: {output_path}")
        return output_path

    handlers = {
        "step-collect": step_collect,
        "step-gateway": step_gateway,
        "step-dns": step_dns,
        "step-internet": step_internet,
        "step-dns-split": step_dns_split,
        "step-cpe-link-routing": step_cpe_link_routing,
        "step-analyze": step_analyze,
        "step-conclusion": step_conclusion,
        "step-report": step_report
    }
    
    # 执行流程
    try:
        runtime = FlowRuntime()
        # 如果禁用并行，可以在 FlowRuntime 中通过配置控制，或者这里修改 flow_def
        flow_def = QUICK_CHECK_FLOW
        if no_parallel:
            # 简单处理：移除并行组配置
            import copy
            flow_def = copy.deepcopy(QUICK_CHECK_FLOW)
            flow_def.config["parallel_groups"] = []
            
        asyncio.run(runtime.execute_flow(flow_def, ctx, handlers))
        
        # 打印摘要
        diagnosis_result = ctx.get("diagnosis_result")
        if diagnosis_result:
            print("")
            summary_text = format_diagnosis_summary(diagnosis_result)
            print(summary_text)
            rec_text = format_recommendations(diagnosis_result.recommendations)
            if rec_text:
                print(rec_text)
                
    except Exception as e:
        logger.error(f"一键体检执行失败: {e}", exc_info=True)
        print(f"\n❌ 执行失败: {e}")
        sys.exit(1)