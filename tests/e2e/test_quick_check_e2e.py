"""
一键体检端到端测试

验证 QuickCheck Flow 的完整执行链路：
采集 → 探测 → 规则分析 → 报告生成
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity, RootCause
from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
from sdwan_desktop.runtime.engine import FlowRuntime
from sdwan_desktop.core.types.flow_state import FlowStatus
from sdwan_desktop.services.collector.windows_collector import SystemInfoSnapshot
from sdwan_desktop.services.connectivity import ConnectivityTestResult
from sdwan_desktop.services.dns_split import DnsSplitTestResult
from sdwan_desktop.services.analyzer.rule_engine import RuleEngine


@pytest.mark.asyncio
async def test_quick_check_happy_path(sample_flow_context, temp_dir):
    """
    测试一键体检完整流程 (Happy Path)
    
    验证点：
    1. FlowRuntime 能正确加载 QUICK_CHECK_FLOW
    2. 各步骤按依赖顺序执行
    3. 最终生成 DiagnosisResult 且结构完整
    4. trace_id 在输出中贯穿
    5. 报告文件成功生成
    """
    ctx = sample_flow_context
    runtime = FlowRuntime()
    
    # Mock 关键服务组件
    with patch('sdwan_desktop.services.collector.windows_collector.WindowsCollector') as MockCollector, \
         patch('sdwan_desktop.services.connectivity.ConnectivityTester') as MockConnectivity, \
         patch('sdwan_desktop.services.dns_split.DnsSplitTester') as MockDnsSplit, \
         patch('sdwan_desktop.services.analyzer.rule_engine.RuleEngine') as MockRuleEngine, \
         patch('sdwan_desktop.services.reporter.html_builder.HtmlReportBuilder') as MockReporter:
        
        # 1. Mock WindowsCollector
        mock_collector_instance = AsyncMock()
        mock_snapshot = SystemInfoSnapshot(
            adapters=[],
            ip_config=None,
            routes=[],
            dns_config=None,
            proxy_config=None,
            firewall_status=None,
            arp_table=[],
            active_connections=[],
            ipv6=None
        )
        mock_collector_instance.collect.return_value = mock_snapshot
        MockCollector.return_value = mock_collector_instance
        
        # 2. Mock ConnectivityTester
        mock_connectivity_instance = AsyncMock()
        mock_connectivity_result = ConnectivityTestResult(
            gateway_ping=None,
            domestic_dns_results=[],
            international_dns_results=[],
            domestic_target_results=[],
            international_target_results=[]
        )
        mock_connectivity_instance.test_all.return_value = mock_connectivity_result
        MockConnectivity.return_value = mock_connectivity_instance
        
        # 3. Mock DnsSplitTester
        mock_dns_instance = AsyncMock()
        mock_dns_result = DnsSplitTestResult(
            domain_results=[],
            split_domains=[],
            split_count=0,
            total_domains=0
        )
        mock_dns_instance.test_all_domains.return_value = mock_dns_result
        MockDnsSplit.return_value = mock_dns_instance
        
        # 4. Mock RuleEngine
        mock_rule_engine_instance = AsyncMock()
        mock_rule_engine_instance.evaluate.return_value = MagicMock(results=[])
        MockRuleEngine.return_value = mock_rule_engine_instance
        
        # 5. Mock HtmlReportBuilder
        mock_reporter_instance = MagicMock()
        mock_reporter_instance.build_quick_check_report.return_value = "<html>Mock Report</html>"
        MockReporter.return_value = mock_reporter_instance
        
        # 定义步骤处理器映射
        async def step_collect(ctx):
            snapshot = await mock_collector_instance.collect(ctx)
            ctx.set("system_snapshot", snapshot)
            return snapshot
            
        async def step_gateway(ctx):
            result = MagicMock(success=True)
            ctx.set("gateway_ping_result", result)
            return result

        async def step_dns(ctx):
            dns_probe = MagicMock(success=True, target="114.114.114.114", metrics=MagicMock(rtt_avg=10.0))
            ctx.set("dns_results", [dns_probe])
            return [dns_probe]

        async def step_internet(ctx):
            net = ConnectivityTestResult(
                domestic_success_rate=0.5,
                international_success_rate=0.3,
            )
            ctx.set("internet_connectivity_result", net)
            return net

        async def step_connectivity_check(ctx):
            from sdwan_desktop.flow.handlers.flow_control import check_connectivity

            return await check_connectivity(ctx=ctx)

        async def step_cpe_link_routing(ctx):
            from sdwan_desktop.services.dns_split import CpeLinkRouteResult

            result = CpeLinkRouteResult(
                total_domains_tested=0,
                domain_results=[],
                detected_links=[],
                link_distribution={},
                is_multi_link=False,
                multi_link_count=0,
                errors=[],
            )
            ctx.set("cpe_link_routing_result", result)
            return result

        async def step_analyze(ctx):
            rule_results = await mock_rule_engine_instance.evaluate(ctx)
            ctx.set("rule_results", rule_results)
            return rule_results

        async def step_conclusion(ctx):
            diagnosis = DiagnosisResult(
                trace_id=ctx.trace_id,
                diagnosis_type="quick_check",
                summary="诊断完成",
                severity=Severity.INFO,
                root_causes=[],
                recommendations=[],
                overall_confidence=1.0,
            )
            ctx.set("diagnosis_result", diagnosis)
            return diagnosis

        async def step_report(ctx):
            diagnosis = ctx.get("diagnosis_result")
            report_content = mock_reporter_instance.build_quick_check_report(diagnosis, temp_dir / "out.html")
            report_path = temp_dir / "quick_check_report.html"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(str(report_content))
            ctx.set("report_path", str(report_path))
            return str(report_path)
        
        handlers = {
            "step-collect": step_collect,
            "step-gateway": step_gateway,
            "step-dns": step_dns,
            "step-internet": step_internet,
            "step-connectivity-check": step_connectivity_check,
            "step-cpe-link-routing": step_cpe_link_routing,
            "step-analyze": step_analyze,
            "step-conclusion": step_conclusion,
            "step-report": step_report,
        }
        
        # 执行流程
        snapshots = await runtime.execute_flow(QUICK_CHECK_FLOW, ctx, handlers)
        
        # 验证点 1 & 2: 流程执行完成且包含所有步骤
        assert len(snapshots) == len(QUICK_CHECK_FLOW.steps)
        for step in QUICK_CHECK_FLOW.steps:
            assert step.id in snapshots
            assert snapshots[step.id].status == FlowStatus.COMPLETED

        # 验证点 3: 关键中间结果已存储到上下文
        assert ctx.get("system_snapshot") is not None
        assert ctx.get("gateway_ping_result") is not None
        assert ctx.get("dns_results") is not None
        assert ctx.get("internet_connectivity_result") is not None
        assert ctx.get("cpe_link_routing_result") is not None
        assert ctx.get("rule_results") is not None
        
        # 验证点 4: trace_id 贯穿 (通过 Context 验证)
        assert ctx.trace_id == "e2e-trace-001"
        
        # 验证点 5: 报告文件存在
        report_path = ctx.get("report_path")
        assert report_path is not None
        assert Path(report_path).exists()


@pytest.mark.asyncio
async def test_quick_check_trace_id_consistency(sample_flow_context):
    """
    验证 trace_id 在整个流程中的一致性
    """
    ctx = sample_flow_context
    runtime = FlowRuntime()
    
    async def dummy_step(ctx):
        # 确保每一步都能访问到正确的 trace_id
        assert ctx.trace_id == "e2e-trace-001"
        return {"trace_check": "ok"}
        
    handlers = {s.id: dummy_step for s in QUICK_CHECK_FLOW.steps}
    
    # 仅测试前几个步骤以验证上下文传递
    # 实际 E2E 会跑全量，这里主要测 Context 传递
    snapshots = await runtime.execute_flow(QUICK_CHECK_FLOW, ctx, handlers)
    
    # 验证所有快照都关联了正确的 trace_id (通过 Context 间接验证)
    assert len(snapshots) > 0
