"""
深度诊断端到端测试

验证 DeepDive Flow 的完整执行链路：
PC采集 → CPE连接 → 配置解析 → 拓扑构建 → 根因分析 → 报告生成
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity, RootCause
from sdwan_desktop.flow.definitions.deep_dive import DEEP_DIVE_FLOW
from sdwan_desktop.runtime.engine import FlowRuntime
from sdwan_desktop.services.collector.windows_collector import SystemInfoSnapshot
from sdwan_desktop.services.topology.topology import NetworkTopology
from sdwan_desktop.services.analyzer.root_cause import RootCauseEngine


@pytest.mark.asyncio
async def test_deep_dive_happy_path(sample_flow_context, temp_dir):
    """
    测试深度诊断完整流程 (Happy Path)
    
    验证点：
    1. PC 和 CPE 采集成功
    2. 拓扑结构正确构建
    3. 根因逻辑合理（即使为空也应返回对象）
    4. 报告文件生成
    """
    ctx = sample_flow_context
    runtime = FlowRuntime()
    
    with patch('sdwan_desktop.services.collector.windows_collector.WindowsCollector') as MockPcCollector, \
         patch('sdwan_desktop.services.collector.cpe_collector.CpeCollector') as MockCpeCollector, \
         patch('sdwan_desktop.services.topology.topology_builder.TopologyBuilder') as MockTopologyBuilder, \
         patch('sdwan_desktop.services.analyzer.root_cause.RootCauseEngine') as MockRootCauseEngine, \
         patch('sdwan_desktop.services.reporter.html_builder.HtmlReportBuilder') as MockReporter:
        
        # 1. Mock PC Collector
        mock_pc_instance = AsyncMock()
        mock_pc_snapshot = SystemInfoSnapshot(
            adapters=[], ip_config=None, routes=[], dns_config=None,
            proxy_config=None, firewall_status=None, arp_table=[],
            active_connections=[], ipv6=None
        )
        mock_pc_instance.collect.return_value = mock_pc_snapshot
        MockPcCollector.return_value = mock_pc_instance
        
        # 2. Mock CPE Collector
        mock_cpe_instance = AsyncMock()
        mock_cpe_result = MagicMock()
        mock_cpe_result.to_dict.return_value = {"vendor": "raisecom", "model": "msg5200"}
        mock_cpe_instance.connect.return_value = True
        mock_cpe_instance.collect_config.return_value = mock_cpe_result
        MockCpeCollector.return_value = mock_cpe_instance
        
        # 3. Mock Topology Builder
        mock_topology_instance = AsyncMock()
        mock_topology = NetworkTopology(nodes=[], edges=[])
        mock_topology_instance.build.return_value = mock_topology
        MockTopologyBuilder.return_value = mock_topology_instance
        
        # 4. Mock Root Cause Engine
        mock_rce_instance = AsyncMock()
        mock_rce_instance.analyze.return_value = []
        MockRootCauseEngine.return_value = mock_rce_instance
        
        # 5. Mock Reporter
        mock_reporter_instance = MagicMock()
        mock_reporter_instance.build_deep_dive_report.return_value = "<html>Deep Dive Report</html>"
        MockReporter.return_value = mock_reporter_instance
        
        # 定义步骤处理器映射
        async def step_pc_collect(ctx):
            snapshot = await mock_pc_instance.collect(ctx)
            ctx.set("pc_snapshot", snapshot)
            return snapshot

        async def step_cpe_connect(ctx):
            # 模拟连接成功，实际参数可能从 ctx 获取，这里简化处理以匹配 Mock
            result = await mock_cpe_instance.connect("192.168.1.1", "admin", "password")
            ctx.set("cpe_connected", result)
            return result

        async def step_cpe_collect(ctx):
            result = await mock_cpe_instance.collect_config(ctx)
            ctx.set("cpe_result", result)
            return result

        async def step_topology_build(ctx):
            pc_data = ctx.get("pc_snapshot")
            cpe_result = ctx.get("cpe_result")
            topology = await mock_topology_instance.build(pc_data, cpe_result)
            ctx.set("topology", topology)
            return topology

        async def step_biz_probe(ctx):
            ctx.set(
                "targeted_probe_pc",
                {"status": "skipped", "data": {}, "error": None, "biz_agg": None},
            )
            return {}

        async def step_cpe_post_probe(ctx):
            ctx.set("targeted_probe", {"status": "skipped", "data": {}, "error": None})
            return {}

        async def step_overlay_policy_flow(ctx):
            ctx.set("overlay_policy_flow", {"status": "ok", "data": {}, "error": None})
            return {}

        async def step_root_cause(ctx):
            topology = ctx.get("topology")
            cpe_result = ctx.get("cpe_result")
            pc_data = ctx.get("pc_snapshot")
            causes = await mock_rce_instance.analyze(
                topology,
                cpe_result,
                pc_data,
                targeted_probe=ctx.get("targeted_probe"),
            )
            ctx.set("root_causes", causes)
            return causes

        async def step_report_gen(ctx):
            causes = ctx.get("root_causes", [])
            topology = ctx.get("topology")
            diagnosis_result = DiagnosisResult(
                trace_id=ctx.trace_id,
                diagnosis_type="deep_dive",
                root_causes=causes,
                severity=Severity.INFO,
                summary="Deep Dive E2E Test",
                overall_confidence=0.9
            )
            
            report_path = temp_dir / "deep_dive_report.html"
            html_content = mock_reporter_instance.build_deep_dive_report(
                diagnosis_result, 
                topology.to_dict() if topology else {}, 
                report_path
            )
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            ctx.set("report_path", report_path)
            return report_path

        handlers = {
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
        
        # 执行流程
        snapshots = await runtime.execute_flow(DEEP_DIVE_FLOW, ctx, handlers)
        
        # 验证点 1: 所有步骤执行成功
        assert len(snapshots) == len(DEEP_DIVE_FLOW.steps)
        for step_id, snapshot in snapshots.items():
            assert snapshot.status.value in ["completed", "COMPLETED"], f"Step {step_id} failed: {snapshot.error}"
        
        # 验证点 2: 拓扑结构正确
        topology = ctx.get("topology")
        assert topology is not None
        assert isinstance(topology, NetworkTopology)
        
        # 验证点 3: 根因分析结果
        root_causes = ctx.get("root_causes")
        assert root_causes is not None
        assert isinstance(root_causes, list)
        
        # 验证点 4: 报告文件存在
        report_path = ctx.get("report_path")
        assert report_path is not None
        assert Path(report_path).exists()


@pytest.mark.asyncio
async def test_deep_dive_cpe_connection_failure(sample_flow_context):
    """
    测试 CPE 连接失败场景
    """
    ctx = sample_flow_context
    runtime = FlowRuntime()
    
    with patch('sdwan_desktop.services.collector.windows_collector.WindowsCollector') as MockPcCollector, \
         patch('sdwan_desktop.services.collector.cpe_collector.CpeCollector') as MockCpeCollector:
        
        mock_pc_instance = AsyncMock()
        mock_pc_instance.collect.return_value = SystemInfoSnapshot(
            adapters=[], ip_config=None, routes=[], dns_config=None,
            proxy_config=None, firewall_status=None, arp_table=[],
            active_connections=[], ipv6=None
        )
        MockPcCollector.return_value = mock_pc_instance
        
        mock_cpe_instance = AsyncMock()
        # 模拟连接失败
        mock_cpe_instance.connect.side_effect = Exception("SSH Connection Refused")
        MockCpeCollector.return_value = mock_cpe_instance
        
        async def step_pc_collect(ctx):
            snapshot = await mock_pc_instance.collect(ctx)
            ctx.set("pc_snapshot", snapshot)
            return snapshot
            
        async def step_cpe_connect(ctx):
            # 模拟连接失败
            result = await mock_cpe_instance.connect("192.168.1.1", "admin", "password")
            ctx.set("cpe_connected", result)
            return result
            
        # 其他步骤省略，因为依赖 step-cpe-connect 失败后通常不会执行（取决于 continue_on_error）
        handlers = {
            "step-pc-collect": step_pc_collect,
            "step-cpe-connect": step_cpe_connect,
            "step-cpe-collect": lambda ctx: None,
            "step-topology-build": lambda ctx: None,
            "step-biz-probe": lambda ctx: None,
            "step-cpe-post-probe": lambda ctx: None,
            "step-overlay-policy-flow": lambda ctx: None,
            "step-root-cause": lambda ctx: None,
            "step-report-gen": lambda ctx: None,
        }
        
        # 由于 DEEP_DIVE_FLOW 默认 continue_on_error=False，这里预期会抛出异常或记录失败快照
        # 在 E2E 中我们通常验证错误是否被正确捕获
        try:
            await runtime.execute_flow(DEEP_DIVE_FLOW, ctx, handlers)
            assert False, "Expected FlowError to be raised"
        except Exception as e:
            # 验证点：错误信息包含原始异常内容或步骤标识
            assert "step-cpe-connect" in str(e) or "SSH Connection Refused" in str(e)
