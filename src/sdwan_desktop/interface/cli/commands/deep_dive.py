"""
深度诊断 CLI 命令 (DeepDive)

提供 PC + CPE 联合诊断功能，支持 SSH/TELNET 连接参数配置。
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.flow.definitions.deep_dive import DEEP_DIVE_FLOW
from sdwan_desktop.runtime.engine import FlowRuntime
from sdwan_desktop.services.collector.windows_collector import WindowsCollector
from sdwan_desktop.services.collector.cpe_collector import CpeCollector, CpeCollectorConfig
from sdwan_desktop.services.topology.topology_builder import TopologyBuilder
from sdwan_desktop.services.analyzer.root_cause import RootCauseEngine
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity, RootCause

logger = logging.getLogger(__name__)


@click.command()
@click.option('--cpe', '-c', required=True, help='CPE 设备 IP 地址')
@click.option('--port', '-p', default=23, help='连接端口 (默认: 23 for Telnet)')
@click.option('--user', '-u', required=True, help='登录用户名')
@click.option('--password', '--pwd', default=None, help='登录密码 (或使用 --key-file)')
@click.option('--key-file', '-k', default=None, help='SSH 私钥文件路径')
@click.option('--protocol', '--proto', default='telnet', help='连接协议 (默认: telnet, 可选: ssh)')
@click.option('--output', '-o', default=None, help='报告输出路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
def deep_dive(cpe: str, port: int, user: str, password: Optional[str], 
              key_file: Optional[str], protocol: str, output: Optional[str], verbose: bool):
    """执行 SD-WAN 深度诊断 (PC + CPE 联合分析)"""
    
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🔍 SD-WAN 深度诊断 v1.0.0")
    
    import uuid
    trace_id = str(uuid.uuid4())
    print(f"Trace ID: {trace_id}")
    print(f"Target CPE: {cpe}:{port} ({user}) via {protocol.upper()}")
    print("")
    
    ctx = FlowContext(trace_id=trace_id)
    
    # 初始化服务
    pc_collector = WindowsCollector()
    cpe_config = CpeCollectorConfig(
        host=cpe, 
        port=port, 
        username=user, 
        password=password, 
        private_key=key_file,
        protocol=protocol  # ✅ 使用指定的协议
    )
    cpe_collector = CpeCollector(config=cpe_config)
    topology_builder = TopologyBuilder()
    root_cause_engine = RootCauseEngine()
    report_builder = HtmlReportBuilder()
    
    async def step_pc_collect(ctx: FlowContext):
        print("📊 [1/6] 采集 PC 端系统信息... ", end="", flush=True)
        snapshot = await pc_collector.collect(ctx)
        ctx.set("pc_snapshot", snapshot)
        print("✓")
        return snapshot

    async def step_cpe_connect(ctx: FlowContext):
        print("🔌 [2/6] 连接 CPE 设备... ", end="", flush=True)
        try:
            # 简化：在 collect 中处理连接和采集
            # 这里为了符合 Flow 定义，先执行连接验证
            is_valid = await cpe_collector.validate(ctx)
            if not is_valid:
                raise Exception("CPE 配置验证失败")
            print("✓")
        except Exception as e:
            print(f"✗ ({e})")
            raise
        return True

    async def step_cpe_collect(ctx: FlowContext):
        print("📡 [3/6] 采集 CPE 配置信息... ", end="", flush=True)
        result = await cpe_collector.collect(ctx)
        ctx.set("cpe_result", result)
        if result.success:
            print("✓")
        else:
            print(f"✗ ({result.error_message})")
        return result

    async def step_topology_build(ctx: FlowContext):
        print("🕸️  [4/6] 构建网络拓扑... ", end="", flush=True)
        pc_data = ctx.get("pc_snapshot").to_dict() if hasattr(ctx.get("pc_snapshot"), 'to_dict') else {}
        cpe_result = ctx.get("cpe_result")
        
        topology = topology_builder.build(pc_data, cpe_result)
        ctx.set("topology", topology)
        print("✓")
        return topology

    async def step_root_cause(ctx: FlowContext):
        print("🧠 [5/6] 执行根因分析... ", end="", flush=True)
        topology = ctx.get("topology")
        cpe_result = ctx.get("cpe_result")
        pc_data = ctx.get("pc_snapshot")
        
        causes = root_cause_engine.analyze(topology, cpe_result, pc_data.to_dict() if hasattr(pc_data, 'to_dict') else {})
        ctx.set("root_causes", causes)
        print(f"✓ (发现 {len(causes)} 个潜在问题)")
        return causes

    async def step_report_gen(ctx: FlowContext):
        print("📝 [6/6] 生成专业报告... ", end="", flush=True)
        causes = ctx.get("root_causes", [])
        topology = ctx.get("topology")
        
        # 构造 DiagnosisResult
        diagnosis_result = DiagnosisResult(
            trace_id=ctx.trace_id,
            diagnosis_type="deep_dive",
            root_causes=causes,
            severity=Severity.CRITICAL if any(c.severity == Severity.CRITICAL for c in causes) else Severity.INFO,
            summary=f"深度诊断完成，共识别出 {len(causes)} 个问题。",
            overall_confidence=0.9
        )
        
        # 确定输出路径
        if output:
            out_path = Path(output)
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = Path("./reports")
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / f"deep_dive_{ts}.html"
            
        try:
            html_content = report_builder.build_deep_dive_report(
                diagnosis_result, 
                topology.to_dict(), 
                out_path
            )
            print("✓")
            print(f"\n📄 报告已保存: {out_path}")
        except Exception as e:
            print(f"✗ ({e})")
            logger.error(f"报告生成失败: {e}", exc_info=True)
            
        return out_path

    handlers = {
        "step-pc-collect": step_pc_collect,
        "step-cpe-connect": step_cpe_connect,
        "step-cpe-collect": step_cpe_collect,
        "step-topology-build": step_topology_build,
        "step-root-cause": step_root_cause,
        "step-report-gen": step_report_gen
    }
    
    try:
        runtime = FlowRuntime()
        asyncio.run(runtime.execute_flow(DEEP_DIVE_FLOW, ctx, handlers))
    except Exception as e:
        logger.error(f"深度诊断执行失败: {e}", exc_info=True)
        print(f"\n❌ 执行失败: {e}")
        sys.exit(1)
