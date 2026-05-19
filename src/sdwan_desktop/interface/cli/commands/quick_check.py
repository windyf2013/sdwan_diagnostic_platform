"""
一键体检 CLI 命令 - 主流程与独立测试命令
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import click

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW, DEFAULT_TEST_DOMAINS
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
from sdwan_desktop.services.connectivity import ProbeTarget, ProbeProtocol

logger = logging.getLogger(__name__)


# ==================== 主流程命令 ====================

@click.command(
    epilog=(
        "成功判据: 流程完成并生成输出文件；严重度由规则引擎汇总。\n"
        "不包含: CPE 配置解析、隧道 BFD、全量策略审计、单业务 SLA 证明。\n"
        "升级: 特定业务 FQDN:端口 → agentctl business-diagnose；CPE 专检 → agentctl deep-dive。\n"
        "退出码: 0 成功；1 运行时错误；2 未使用。\n"
        "JSON（--format json）: 顶层含 diagnosis 与 report_pack，供 CI 门禁。"
    ),
)
@click.option('--output', '-o', default=None, help='报告输出路径 (默认: ./reports/quick_check_<timestamp>.html；JSON 时为 .json)')
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

    from pydantic import ValidationError
    from sdwan_desktop.core.types.quick_check_run_config import QuickCheckRunConfig

    try:
        cfg = QuickCheckRunConfig(output_format=str(fmt).lower(), report_output=output)
    except ValidationError as exc:
        print(f"参数无效: {exc}")
        sys.exit(1)

    ctx.set("output_format", cfg.output_format)

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
    
    from sdwan_desktop.flow.handlers.quick_check_steps import (
        QuickCheckHandlerDeps,
        QuickCheckHandlersParams,
        build_quick_check_step_handlers,
    )

    step_handlers = build_quick_check_step_handlers(
        QuickCheckHandlerDeps(
            collector=collector,
            connectivity_tester=connectivity_tester,
            dns_split_tester=dns_split_tester,
            rule_engine=rule_engine,
            report_builder=report_builder,
        ),
        QuickCheckHandlersParams(
            report_output=Path(cfg.report_output) if cfg.report_output else None,
            output_format=cfg.output_format,
            console=True,
        ),
    )

    # 运行 Flow
    print("="*60)
    print("开始执行一键体检流程")
    print("="*60)
    print()
    
    # ✅ 修复：FlowRuntime不接受参数，execute_flow方法接受flow_def
    runtime = FlowRuntime()
    
    try:
        # 异步运行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # ✅ 修复：使用正确的API调用方式
        loop.run_until_complete(
            runtime.execute_flow(
                flow_def=QUICK_CHECK_FLOW,
                ctx=ctx,
                handlers=step_handlers
            )
        )

        print("\n" + "="*60)
        print("体检完成！")
        print("="*60)

        # 显示诊断摘要（数据在 FlowContext 上，非 execute_flow 返回值）
        diagnosis = ctx.get("diagnosis_result")
        if diagnosis:
            print(format_diagnosis_summary(diagnosis))
            
            if diagnosis.recommendations:
                print("\n" + format_recommendations(diagnosis.recommendations))
        
    except Exception as e:
        print(f"\n❌ 流程执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@click.command()
@click.option('--domains', '-d', default=None, help='测试域名列表（逗号分隔，默认使用统一域名集）')
@click.option('--domestic-dns', default='114.114.114.114,223.5.5.5', help='国内DNS服务器（逗号分隔）')
@click.option('--international-dns', default='8.8.8.8,1.1.1.1', help='国际DNS服务器（逗号分隔）')
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
def dns_split_test(domains: Optional[str], domestic_dns: str, international_dns: str, verbose: bool):
    """独立运行 DNS 分流测试模块
    
    用于单独测试国内外 DNS 解析差异，无需执行完整的一键体检流程。
    
    示例：
        # 使用默认配置
        python -m sdwan_desktop.interface.cli.main dns-split-test
        
        # 指定自定义域名
        python -m sdwan_desktop.interface.cli.main dns-split-test -d "www.baidu.com,www.google.com"
        
        # 指定自定义 DNS 服务器
        python -m sdwan_desktop.interface.cli.main dns-split-test --domestic-dns "114.114.114.114" --international-dns "8.8.8.8"
    """
    import uuid
    
    # 设置日志
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🔍 DNS 分流独立测试模块")
    print("=" * 60)
    
    # 创建 FlowContext
    ctx = FlowContext(trace_id=str(uuid.uuid4()))
    
    # 解析域名列表
    from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS
    
    if domains:
        test_domains = [d.strip() for d in domains.split(',') if d.strip()]
    else:
        test_domains = DEFAULT_TEST_DOMAINS
    
    print(f"\n📋 测试配置:")
    print(f"   - 测试域名: {len(test_domains)} 个")
    for i, domain in enumerate(test_domains, 1):
        print(f"     {i}. {domain}")
    
    # 解析 DNS 服务器列表
    domestic_dns_list = [dns.strip() for dns in domestic_dns.split(',') if dns.strip()]
    international_dns_list = [dns.strip() for dns in international_dns.split(',') if dns.strip()]
    
    print(f"\n   - 国内DNS: {', '.join(domestic_dns_list)}")
    print(f"   - 国际DNS: {', '.join(international_dns_list)}")
    
    # 创建测试器并执行
    async def run_test():
        start_time = datetime.now()
        
        print(f"\n🚀 开始执行 DNS 分流测试...")
        print("-" * 60)
        
        result = await dns_split_tester.test_optimized(
            domains=test_domains,
            domestic_dns=domestic_dns_list,
            international_dns=international_dns_list,
            ctx=ctx,
            use_cache=False  # 独立测试不使用缓存
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # 输出结果摘要
        print("\n" + "=" * 60)
        print(f"✅ 测试完成 (耗时: {duration:.1f}s)")
        print("=" * 60)
        
        split_count = sum(1 for dr in result.domain_results if dr.is_split)
        consistent_count = len(result.domain_results) - split_count
        
        print(f"\n📊 测试结果摘要:")
        print(f"   - 总测试域名数: {len(result.domain_results)}")
        print(f"   - 全球一致: {consistent_count} 个")
        print(f"   - 存在地域差异: {split_count} 个")
        
        if split_count > 0:
            print(f"\n⚠️  发现分流异常的域名:")
            for dr in result.domain_results:
                if dr.is_split:
                    print(f"   - {dr.domain}: {dr.split_description}")
        else:
            print(f"\n✅ 所有域名解析全球一致，未发现 DNS 分流异常")
        
        if verbose:
            print(f"\n📝 详细结果:")
            for dr in result.domain_results:
                print(f"\n   [{dr.domain}]")
                print(f"     是否分流: {'是' if dr.is_split else '否'}")
                print(f"     国内解析: {dr.domestic_results}")
                print(f"     国际解析: {dr.international_results}")
                print(f"     耗时: {dr.total_duration_ms:.0f}ms")
        
        return result
    
    try:
        asyncio.run(run_test())
    except Exception as e:
        logger.error(f"DNS 分流测试失败: {e}", exc_info=True)
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)


# ==================== 独立测试命令 ====================

@click.command()
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
@click.option('--output', '-o', default=None, help='输出JSON文件路径（可选）')
def system_collect(verbose: bool, output: Optional[str]):
    """独立运行系统信息采集模块
    
    采集Windows网络配置信息，包括网卡、路由、DNS等。
    
    示例：
        python -m sdwan_desktop.interface.cli.main system-collect
        python -m sdwan_desktop.interface.cli.main system-collect --verbose -o snapshot.json
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("📊 系统信息采集模块")
    print("=" * 60)
    
    import uuid
    ctx = FlowContext(trace_id=str(uuid.uuid4()))
    collector = WindowsCollector()
    
    try:
        print("\n🚀 开始采集系统信息...")
        print("-" * 60)
        
        snapshot = asyncio.run(collector.collect(ctx))
        
        print(f"\n✅ 采集完成！")
        print(f"   - Trace ID: {ctx.trace_id}")
        print(f"   - 网卡数量: {len(snapshot.adapters)}")
        print(f"   - 路由数量: {len(snapshot.routes)}")
        print(f"   - ARP表项: {len(snapshot.arp_table)}")
        
        if snapshot.primary_adapter:
            primary = snapshot.primary_adapter
            print(f"\n🔍 主网卡信息:")
            print(f"   - 名称: {primary.description or primary.name}")
            print(f"   - 状态: {'已连接' if primary.is_connected else '未连接'}")
            print(f"   - IP地址: {', '.join(primary.ip_addresses) if primary.ip_addresses else '无'}")
            print(f"   - 默认网关: {primary.default_gateway or '无'}")
            print(f"   - DNS服务器: {', '.join(primary.dns_servers) if primary.dns_servers else '无'}")
        
        if snapshot.ip_config:
            print(f"\n🌐 IP配置:")
            print(f"   - 默认网关: {snapshot.ip_config.default_gateway or '无'}")
            print(f"   - DNS服务器: {', '.join(snapshot.ip_config.dns_servers) if snapshot.ip_config.dns_servers else '无'}")
        
        if output:
            import json
            from dataclasses import asdict
            
            # 转换为可序列化的字典
            snapshot_dict = {
                "trace_id": snapshot.trace_id,
                "timestamp": datetime.now().isoformat(),
                "adapters_count": len(snapshot.adapters),
                "routes_count": len(snapshot.routes),
                "arp_table_count": len(snapshot.arp_table),
                "primary_adapter": {
                    "name": snapshot.primary_adapter.name if snapshot.primary_adapter else None,
                    "description": snapshot.primary_adapter.description if snapshot.primary_adapter else None,
                    "is_connected": snapshot.primary_adapter.is_connected if snapshot.primary_adapter else None,
                    "ip_addresses": snapshot.primary_adapter.ip_addresses if snapshot.primary_adapter else [],
                    "default_gateway": snapshot.primary_adapter.default_gateway if snapshot.primary_adapter else None,
                    "dns_servers": snapshot.primary_adapter.dns_servers if snapshot.primary_adapter else [],
                } if snapshot.primary_adapter else None,
                "ip_config": {
                    "default_gateway": snapshot.ip_config.default_gateway if snapshot.ip_config else None,
                    "dns_servers": snapshot.ip_config.dns_servers if snapshot.ip_config else [],
                } if snapshot.ip_config else None,
            }
            
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(snapshot_dict, f, ensure_ascii=False, indent=2)
            print(f"\n💾 结果已保存至: {output}")
        
    except Exception as e:
        logger.error(f"系统信息采集失败: {e}", exc_info=True)
        print(f"\n❌ 采集失败: {e}")
        sys.exit(1)


@click.command()
@click.option('--gateway', '-g', default=None, help='网关IP地址（默认自动检测）')
@click.option('--count', '-c', default=4, help='Ping次数（默认4次）')
@click.option('--timeout', '-t', default=10, help='超时时间（秒，默认10秒）')
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
def gateway_test(gateway: Optional[str], count: int, timeout: int, verbose: bool):
    """独立运行网关连通性测试模块
    
    测试默认网关的可达性和延迟。
    
    示例：
        python -m sdwan_desktop.interface.cli.main gateway-test
        python -m sdwan_desktop.interface.cli.main gateway-test -g 192.168.1.1 -c 10
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("🌐 网关连通性测试模块")
    print("=" * 60)
    
    import uuid
    ctx = FlowContext(trace_id=str(uuid.uuid4()))
    tester = ConnectivityTester()
    
    # 如果未指定网关，先采集系统信息获取
    if not gateway:
        print("\n🔍 未指定网关，正在自动检测...")
        collector = WindowsCollector()
        try:
            snapshot = asyncio.run(collector.collect(ctx))
            if snapshot.primary_adapter and snapshot.primary_adapter.default_gateway:
                gateway = snapshot.primary_adapter.default_gateway
                print(f"   ✅ 检测到网关: {gateway}")
            elif snapshot.ip_config and snapshot.ip_config.default_gateway:
                gateway = snapshot.ip_config.default_gateway
                print(f"   ✅ 检测到网关: {gateway}")
            else:
                print(f"   ❌ 未检测到网关，请使用 -g 参数手动指定")
                sys.exit(1)
        except Exception as e:
            print(f"   ❌ 自动检测失败: {e}")
            sys.exit(1)
    
    try:
        print(f"\n🚀 开始测试网关 {gateway}...")
        print(f"   - Ping次数: {count}")
        print(f"   - 超时时间: {timeout}秒")
        print("-" * 60)
        
        target = ProbeTarget(
            host=gateway,
            protocol=ProbeProtocol.ICMP,
            count=count,
            timeout_seconds=timeout,
        )
        
        result = asyncio.run(tester._execute_probe(target, ctx))
        
        print(f"\n{'✅' if result.success else '❌'} 测试完成！")
        print(f"   - 目标: {gateway}")
        print(f"   - 状态: {'可达' if result.success else '不可达'}")
        print(f"   - 耗时: {result.duration_ms:.0f}ms")
        
        if result.metrics:
            if result.metrics.rtt_avg is not None:
                print(f"   - 平均RTT: {result.metrics.rtt_avg:.1f}ms")
            if result.metrics.rtt_min is not None:
                print(f"   - 最小RTT: {result.metrics.rtt_min:.1f}ms")
            if result.metrics.rtt_max is not None:
                print(f"   - 最大RTT: {result.metrics.rtt_max:.1f}ms")
            if result.metrics.loss_rate is not None:
                print(f"   - 丢包率: {result.metrics.loss_rate:.1%}")
        
        if result.error_message:
            print(f"   - 错误: {result.error_message}")
        
        if not result.success:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"网关测试失败: {e}", exc_info=True)
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)


@click.command()
@click.option('--dns-servers', '-d', default='114.114.114.114,8.8.8.8', help='DNS服务器列表（逗号分隔）')
@click.option('--domain', '-D', default='www.baidu.com', help='测试域名（默认www.baidu.com）')
@click.option('--count', '-c', default=2, help='每个DNS的查询次数（默认2次）')
@click.option('--timeout', '-t', default=5, help='超时时间（秒，默认5秒）')
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
def dns_resolve(dns_servers: str, domain: str, count: int, timeout: int, verbose: bool):
    """独立运行DNS解析测试模块
    
    测试DNS服务器的解析能力和响应时间。
    
    示例：
        python -m sdwan_desktop.interface.cli.main dns-resolve
        python -m sdwan_desktop.interface.cli.main dns-resolve -d "114.114.114.114,8.8.8.8" -D www.google.com
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("🔬 DNS解析测试模块")
    print("=" * 60)
    
    import uuid
    ctx = FlowContext(trace_id=str(uuid.uuid4()))
    tester = ConnectivityTester()
    
    dns_list = [s.strip() for s in dns_servers.split(',')]
    
    try:
        print(f"\n🚀 开始测试DNS解析...")
        print(f"   - DNS服务器: {', '.join(dns_list)}")
        print(f"   - 测试域名: {domain}")
        print(f"   - 查询次数: {count}/服务器")
        print("-" * 60)
        
        targets = [
            ProbeTarget(
                host=dns,
                protocol=ProbeProtocol.DNS,
                count=count,
                timeout_seconds=timeout,
                dns_server=dns,
            )
            for dns in dns_list
        ]
        
        results = asyncio.run(tester._execute_probes_concurrent(targets, ctx))
        
        print(f"\n✅ 测试完成！")
        success_count = sum(1 for r in results if r.success)
        print(f"   - 成功: {success_count}/{len(results)}")
        
        for i, res in enumerate(results):
            status = "✅ 响应正常" if res.success else "❌ 超时/失败"
            print(f"\n   📍 DNS服务器 {i+1}: {res.target.host}")
            print(f"      状态: {status}")
            print(f"      耗时: {res.duration_ms:.0f}ms")
            
            if res.success and res.metrics:
                if res.metrics.rtt_avg is not None:
                    print(f"      平均RTT: {res.metrics.rtt_avg:.1f}ms")
                if res.metrics.resolved_ips:
                    print(f"      解析IP: {', '.join(res.metrics.resolved_ips[:3])}")
            
            if res.error_message:
                print(f"      错误: {res.error_message}")
        
        if success_count == 0:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"DNS测试失败: {e}", exc_info=True)
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)


@click.command()
@click.option('--domains', '-D', default=None, help='测试域名列表（逗号分隔，默认使用预设域名集）')
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
@click.option('--no-cache', is_flag=True, help='禁用缓存（强制重新探测）')
def internet_test(domains: Optional[str], verbose: bool, no_cache: bool):
    """独立运行互联网连通性测试模块
    
    测试国内外域名的TCP连通性（443端口）。
    
    示例：
        python -m sdwan_desktop.interface.cli.main internet-test
        python -m sdwan_desktop.interface.cli.main internet-test -D "www.baidu.com,www.google.com"
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("🌐 互联网连通性测试模块")
    print("=" * 60)
    
    import uuid
    ctx = FlowContext(trace_id=str(uuid.uuid4()))
    tester = ConnectivityTester()
    
    # 解析域名列表
    if domains:
        test_domains = [d.strip() for d in domains.split(',')]
    else:
        test_domains = DEFAULT_TEST_DOMAINS
        print(f"\nℹ️  使用预设域名集（{len(test_domains)}个域名）")
    
    try:
        print(f"\n🚀 开始测试互联网连通性...")
        print(f"   - 测试域名: {', '.join(test_domains)}")
        print(f"   - 测试协议: TCP (443端口)")
        print("-" * 60)
        
        result = asyncio.run(tester.test_internet_optimized(
            domains=test_domains,
            ctx=ctx,
            use_cache=not no_cache
        ))
        
        print(f"\n✅ 测试完成！")
        
        domestic_ok = sum(1 for t in result.domestic_target_results if t.success)
        international_ok = sum(1 for t in result.international_target_results if t.success)
        domestic_total = len(result.domestic_target_results)
        international_total = len(result.international_target_results)
        
        print(f"\n📊 国内域名成功率: {domestic_ok}/{domestic_total} ({result.domestic_success_rate:.0%})")
        for res in result.domestic_target_results:
            status = "✅" if res.success else "❌"
            rtt_str = f" RTT={res.metrics.rtt_avg:.0f}ms" if res.success and res.metrics and res.metrics.rtt_avg else ""
            print(f"   {status} {res.target.host}{rtt_str}")
        
        print(f"\n📊 国际域名成功率: {international_ok}/{international_total} ({result.international_success_rate:.0%})")
        for res in result.international_target_results:
            status = "✅" if res.success else "❌"
            rtt_str = f" RTT={res.metrics.rtt_avg:.0f}ms" if res.success and res.metrics and res.metrics.rtt_avg else ""
            print(f"   {status} {res.target.host}{rtt_str}")
        
        if result.domestic_success_rate < 0.5 or result.international_success_rate < 0.5:
            print(f"\n⚠️  警告: 部分域名连通性较差")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"互联网连通性测试失败: {e}", exc_info=True)
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)


@click.command()
@click.option('--domains', '-D', default=None, help='测试域名列表（逗号分隔，默认使用预设域名集）')
@click.option('--domestic-dns', default=None, help='国内DNS服务器（逗号分隔）')
@click.option('--international-dns', default='8.8.8.8,1.1.1.1', help='国际DNS服务器（逗号分隔，默认8.8.8.8,1.1.1.1）')
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
@click.option('--no-cache', is_flag=True, help='禁用缓存（强制重新探测）')
def dns_split_test(domains: Optional[str], domestic_dns: Optional[str], international_dns: str, verbose: bool, no_cache: bool):
    """独立运行DNS分流测试模块
    
    对比国内外DNS对同一域名的解析结果差异。
    
    示例：
        python -m sdwan_desktop.interface.cli.main dns-split-test
        python -m sdwan_desktop.interface.cli.main dns-split-test -D "www.google.com,www.baidu.com"
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("🔎 DNS分流测试模块")
    print("=" * 60)
    
    import uuid
    ctx = FlowContext(trace_id=str(uuid.uuid4()))
    tester = DnsSplitTester()
    
    # 解析域名列表
    if domains:
        test_domains = [d.strip() for d in domains.split(',')]
    else:
        test_domains = DEFAULT_TEST_DOMAINS
        print(f"\nℹ️  使用预设域名集（{len(test_domains)}个域名）")
    
    # 解析DNS服务器列表
    if domestic_dns:
        domestic_dns_list = [d.strip() for d in domestic_dns.split(',')]
    else:
        # 从系统获取
        collector = WindowsCollector()
        try:
            snapshot = asyncio.run(collector.collect(ctx))
            domestic_dns_list = snapshot.ip_config.dns_servers if snapshot and snapshot.ip_config else ["114.114.114.114"]
            print(f"\nℹ️  使用系统DNS: {', '.join(domestic_dns_list)}")
        except:
            domestic_dns_list = ["114.114.114.114"]
            print(f"\nℹ️  使用默认DNS: {', '.join(domestic_dns_list)}")
    
    international_dns_list = [d.strip() for d in international_dns.split(',')]
    
    try:
        print(f"\n🚀 开始测试DNS分流...")
        print(f"   - 测试域名: {', '.join(test_domains)}")
        print(f"   - 国内DNS: {', '.join(domestic_dns_list)}")
        print(f"   - 国际DNS: {', '.join(international_dns_list)}")
        print("-" * 60)
        
        result = asyncio.run(tester.test_optimized(
            domains=test_domains,
            domestic_dns=domestic_dns_list,
            international_dns=international_dns_list,
            ctx=ctx,
            use_cache=not no_cache
        ))
        
        print(f"\n✅ 测试完成！")
        
        split_count = sum(1 for dr in result.domain_results if dr.is_split)
        print(f"\n📊 分流统计:")
        print(f"   - 总域名数: {len(result.domain_results)}")
        print(f"   - 存在分流: {split_count}")
        print(f"   - 全球一致: {len(result.domain_results) - split_count}")
        
        if split_count > 0:
            print(f"\n⚠️  发现以下域名存在分流差异:")
            for dr in result.domain_results:
                if dr.is_split:
                    print(f"\n   🌍 {dr.domain}")
                    
                    # ✅ 修复：从字典中提取所有DNS服务器的解析结果并合并
                    domestic_ips = []
                    for dns_server, ips in dr.domestic_results.items():
                        if isinstance(ips, list):
                            # 过滤掉错误信息
                            domestic_ips.extend([ip for ip in ips if not ip.startswith("ERROR:")])
                    
                    international_ips = []
                    for dns_server, ips in dr.international_results.items():
                        if isinstance(ips, list):
                            # 过滤掉错误信息
                            international_ips.extend([ip for ip in ips if not ip.startswith("ERROR:")])
                    
                    print(f"      国内DNS解析: {', '.join(domestic_ips[:3]) if domestic_ips else '无'}")
                    print(f"      国际DNS解析: {', '.join(international_ips[:3]) if international_ips else '无'}")
                    print(f"      说明: {dr.split_description}")
        else:
            print(f"\n✅ 所有域名解析全球一致")
        
    except Exception as e:
        logger.error(f"DNS分流测试失败: {e}", exc_info=True)
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)


@click.command()
@click.option('--domains', '-D', default=None, help='测试域名列表（逗号分隔，默认使用预设域名集）')
@click.option('--max-hops', '-m', default=None, type=int, help='Traceroute最大跳数（默认自动识别）')
@click.option('--cpe-exit-hop', default=2, type=int, help='CPE出口跳点（默认2）')
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
@click.option('--no-cache', is_flag=True, help='禁用缓存（强制重新探测）')
def cpe_link_test(domains: Optional[str], max_hops: Optional[int], cpe_exit_hop: int, verbose: bool, no_cache: bool):
    """独立运行CPE链路分流检测模块
    
    通过Traceroute检测CPE设备对不同域名的链路分流情况。
    
    示例：
        python -m sdwan_desktop.interface.cli.main cpe-link-test
        python -m sdwan_desktop.interface.cli.main cpe-link-test -D "www.baidu.com,www.google.com" -m 15
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("🛣️ CPE链路分流检测模块")
    print("=" * 60)
    
    import uuid
    ctx = FlowContext(trace_id=str(uuid.uuid4()))
    tester = DnsSplitTester()
    
    # 解析域名列表
    if domains:
        test_domains = [d.strip() for d in domains.split(',')]
    else:
        test_domains = DEFAULT_TEST_DOMAINS
        print(f"\nℹ️  使用预设域名集（{len(test_domains)}个域名）")
    
    try:
        print(f"\n🚀 开始检测CPE链路分流...")
        print(f"   - 测试域名: {', '.join(test_domains)}")
        print(f"   - 最大跳数: {max_hops or '自动'}")
        print(f"   - CPE出口跳点: {cpe_exit_hop}")
        print(f"   - 预计耗时: 约{len(test_domains) * 30}秒")
        print("-" * 60)
        
        start_time = datetime.now()
        result = asyncio.run(tester.test_cpe_link_routing_optimized(
            domains=test_domains,
            max_hops=max_hops,
            cpe_exit_hop=cpe_exit_hop,
            ctx=ctx,
            use_cache=not no_cache
        ))
        duration = (datetime.now() - start_time).total_seconds()
        
        print(f"\n✅ 检测完成！（耗时{duration:.1f}秒）")
        
        print(f"\n📊 链路统计:")
        print(f"   - 测试域名数: {result.total_domains_tested}")
        print(f"   - 检测到链路数: {result.multi_link_count}")
        
        if result.is_multi_link:
            print(f"\n🌐 检测到多链路分流:")
            for link_fp, domains_in_link in result.link_distribution.items():
                print(f"\n   🔗 链路 [{link_fp}]")
                print(f"      域名: {', '.join(domains_in_link)}")
        else:
            print(f"\n✅ 所有域名使用相同网络路径")
        
        if result.errors:
            print(f"\n⚠️  警告信息:")
            for error in result.errors:
                print(f"   - {error}")
        
    except Exception as e:
        logger.error(f"CPE链路分流检测失败: {e}", exc_info=True)
        print(f"\n❌ 检测失败: {e}")
        sys.exit(1)


@click.command()
@click.option('--evidence', '-e', required=True, help='证据链JSON文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
def rule_analyze(evidence: str, verbose: bool):
    """独立运行规则分析模块
    
    基于证据链数据进行规则匹配和异常检测。
    
    示例：
        python -m sdwan_desktop.interface.cli.main rule-analyze -e evidence.json
    """
    import json
    
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("📈 规则分析模块")
    print("=" * 60)
    
    try:
        with open(evidence, 'r', encoding='utf-8') as f:
            evidence_data = json.load(f)
        
        print(f"\n📂 加载证据链: {evidence}")
        print(f"   - Trace ID: {evidence_data.get('trace_id', 'N/A')}")
        
        # 初始化规则引擎
        rule_engine = RuleEngine()
        rule_engine.register_rules(GATEWAY_RULES)
        rule_engine.register_rules(DNS_RULES)
        rule_engine.register_rules(SYSTEM_RULES)
        rule_engine.register_rules(CONNECTIVITY_RULES)
        
        print(f"\n🚀 开始执行规则分析...")
        print(f"   - 已注册规则数: {len(rule_engine.rules)}")
        print("-" * 60)
        
        # 注意：这里假设 engine.analyze 接受字典或类似结构，如果实际接口不同需调整
        # 根据现有代码，RuleEngine 通常处理 RuleEvaluationResult，但这里我们模拟从JSON加载后的分析
        # 由于原代码中 analyze 是在 step_analyze 中调用的，且依赖 ctx 中的数据
        # 这里的独立命令主要用于演示或离线分析，具体实现取决于 RuleEngine 的具体接口
        # 假设我们可以直接调用 register_rules 然后执行某种评估
        
        # 由于缺乏具体的离线分析接口，这里仅做占位或简单提示
        # 在实际项目中，可能需要将 JSON 转换回 DiagnosisEvidence 对象列表
        print("⚠️ 离线规则分析功能需要进一步适配证据链对象还原")
        print("   当前仅支持在线流程中的实时分析")
        
    except FileNotFoundError:
        print(f"\n❌ 文件不存在: {evidence}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"规则分析失败: {e}", exc_info=True)
        print(f"\n❌ 分析失败: {e}")
        sys.exit(1)


@click.command()
@click.option('--evidence', '-e', required=True, help='证据链JSON文件路径')
@click.option('--output', '-o', default='report.html', help='报告输出路径（默认report.html）')
@click.option('--format', '-f', 'fmt', default='html', type=click.Choice(['html', 'json']), help='输出格式（默认html）')
def report_gen(evidence: str, output: str, fmt: str):
    """独立运行报告生成模块
    
    基于证据链数据生成HTML或JSON报告。
    
    示例：
        python -m sdwan_desktop.interface.cli.main report-gen -e evidence.json -o report.html
        python -m sdwan_desktop.interface.cli.main report-gen -e evidence.json -o report.json --format json
    """
    import json
    
    log_level = logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("📄 报告生成模块")
    print("=" * 60)
    
    try:
        with open(evidence, 'r', encoding='utf-8') as f:
            evidence_data = json.load(f)
        
        print(f"\n📂 加载证据链: {evidence}")
        print(f"   - Trace ID: {evidence_data.get('trace_id', 'N/A')}")
        
        builder = HtmlReportBuilder()
        
        print(f"\n🚀 开始生成{fmt.upper()}报告...")
        print("-" * 60)
        
        if fmt == 'html':
            # 注意：build_quick_check_report 期望 DiagnosisResult 对象
            # 离线生成需要从 JSON 还原对象，或者使用 build_html_report (如果存在且接受 dict)
            # 这里假设存在一个通用的 build_html_report 或者我们需要还原对象
            # 由于原代码中 HtmlReportBuilder 主要使用 build_quick_check_report(result: DiagnosisResult, path)
            # 我们这里简化处理，提示用户该功能依赖于对象还原
            
            print("⚠️ HTML报告生成通常需要完整的 DiagnosisResult 对象")
            print("   当前仅支持在线流程中的实时报告生成")
        else:
            # JSON格式可以直接输出
            output_path = Path(output)
            output_path.write_text(json.dumps(evidence_data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"✅ JSON报告已保存至: {output_path.absolute()}")
        
    except FileNotFoundError:
        print(f"\n❌ 文件不存在: {evidence}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"报告生成失败: {e}", exc_info=True)
        print(f"\n❌ 生成失败: {e}")
        sys.exit(1)
