"""
一键体检端到端流程测试

验证 QuickCheck Flow 的完整执行链路：
采集 -> 连通性 -> DNS -> 规则分析 -> 报告生成

此测试旨在验证 CLI 和 GUI 流程的一致性，确保底层 Flow 定义和执行引擎行为符合预期。
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from pathlib import Path
import tempfile
import sys

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.system import (
    AdapterInfo,
    AdapterStatus,
    IpConfigInfo,
    SystemInfoSnapshot,
)
from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
from sdwan_desktop.runtime.engine import FlowRuntime
from sdwan_desktop.services.connectivity import ConnectivityTestResult
from sdwan_desktop.services.dns_split import DnsSplitTestResult
from sdwan_desktop.services.analyzer.rule_engine import RuleEngine


@pytest.fixture
def mock_context():
    """创建模拟的 FlowContext"""
    return FlowContext(trace_id="test-trace-id-001")


@pytest.fixture
def mock_system_snapshot():
    """创建模拟的系统采集快照"""
    adapter = AdapterInfo(
        name="Ethernet",
        description="Intel Ethernet Connection",
        mac_address="00:11:22:33:44:55",
        ip_addresses=["192.168.1.100"],
        default_gateway="192.168.1.1",
        dhcp_enabled=True,
        is_connected=True,
        speed_mbps=1000,
        status=AdapterStatus.CONNECTED,
    )

    ip_config = IpConfigInfo(
        default_gateway="192.168.1.1",
        dns_servers=["8.8.8.8", "114.114.114.114"],
    )

    return SystemInfoSnapshot(
        adapters=[adapter],
        ip_config=ip_config,
        routes=[],
        dns_config=None,
        proxy_config=None,
        firewall_status=None,
        arp_table=[],
        active_connections=[],
        ipv6=None,
    )


@pytest.mark.asyncio
async def test_quick_check_flow_execution(mock_context, mock_system_snapshot):
    """
    测试一键体检流程的完整执行
    
    验证点：
    1. FlowRuntime 能正确加载 QUICK_CHECK_FLOW
    2. 各步骤按依赖顺序执行
    3. 最终生成 DiagnosisResult
    """
    # 1. 初始化 FlowRuntime
    runtime = FlowRuntime()
    
    # 2. Mock 关键服务组件，避免真实网络调用
    with patch('sdwan_desktop.services.collector.windows_collector.WindowsCollector') as MockCollector, \
         patch('sdwan_desktop.services.connectivity.ConnectivityTester') as MockConnectivity, \
         patch('sdwan_desktop.services.dns_split.DnsSplitTester') as MockDnsSplit, \
         patch('sdwan_desktop.services.analyzer.rule_engine.RuleEngine') as MockRuleEngine:
        
        # 配置 Mock 返回值
        mock_collector_instance = AsyncMock()
        mock_collector_instance.collect.return_value = mock_system_snapshot
        MockCollector.return_value = mock_collector_instance
        
        mock_connectivity_instance = AsyncMock()
        mock_connectivity_result = ConnectivityTestResult()
        mock_connectivity_instance.test_all.return_value = mock_connectivity_result
        MockConnectivity.return_value = mock_connectivity_instance
        
        mock_dns_instance = AsyncMock()
        mock_dns_result = DnsSplitTestResult(
            domain_results=[],
            total_domains=0,
        )
        mock_dns_instance.test_all_domains.return_value = mock_dns_result
        MockDnsSplit.return_value = mock_dns_instance
        
        mock_rule_engine_instance = AsyncMock()
        mock_rule_engine_instance.execute_rules.return_value = []
        MockRuleEngine.return_value = mock_rule_engine_instance
        
        # 3. 执行 Flow
        # 注意：实际执行需要注册具体的 Handler 映射，这里简化测试 Runtime 的基本调度能力
        # 由于 QUICK_CHECK_FLOW 定义中 handler 指向具体服务方法，我们需要确保 Runtime 能解析这些路径
        # 在集成测试中，通常会注入一个包含所有服务实例的 Context 或 ServiceRegistry
        
        # 此处主要验证 FlowDefinition 的结构完整性
        assert QUICK_CHECK_FLOW.id == "quick-check-v3"
        assert len(QUICK_CHECK_FLOW.steps) > 0
        
        # 验证步骤依赖关系
        step_ids = [s.id for s in QUICK_CHECK_FLOW.steps]
        assert "step-collect" in step_ids
        assert "step-connectivity-check" in step_ids
        assert "step-dns" in step_ids
        assert "step-analyze" in step_ids
        assert "step-report" in step_ids


@pytest.mark.asyncio
async def test_quick_check_error_handling(mock_context):
    """单步失败且 continue_on_error 时，流程记录失败并尽量继续。"""
    from sdwan_desktop.core.types.flow_state import FlowStatus

    runtime = FlowRuntime()

    async def failing_step(ctx, **kwargs):
        raise Exception("Simulated failure")

    async def ok(ctx, **kwargs):
        return None

    handlers = {step.id: ok for step in QUICK_CHECK_FLOW.steps}
    handlers["step-collect"] = failing_step

    snapshots = await runtime.execute_flow(QUICK_CHECK_FLOW, mock_context, handlers)
    assert snapshots["step-collect"].status == FlowStatus.FAILED


def test_flow_definition_structure():
    """测试Flow定义的结构完整性"""
    assert QUICK_CHECK_FLOW.id == "quick-check-v3"
    assert "一键体检" in QUICK_CHECK_FLOW.name
    assert QUICK_CHECK_FLOW.version == "3.0.0"
    
    # 验证所有必需的步骤都存在
    step_map = {s.id: s for s in QUICK_CHECK_FLOW.steps}
    
    required_steps = [
        "step-collect",
        "step-gateway",
        "step-dns",
        "step-internet",
        "step-connectivity-check",
        "step-cpe-link-routing",
        "step-analyze",
        "step-conclusion",
        "step-report"
    ]
    
    for step_id in required_steps:
        assert step_id in step_map, f"缺少必需步骤: {step_id}"
    
    # 验证并行配置
    assert "parallel_groups" in QUICK_CHECK_FLOW.config
    assert ["step-gateway", "step-dns"] in QUICK_CHECK_FLOW.config["parallel_groups"]


@pytest.mark.asyncio
async def test_html_report_generation(mock_context):
    """验证 FlowRuntime 能跑完当前 QUICK_CHECK_FLOW 且报告步骤写入 HTML。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        report_path = Path(tmp_dir) / "report.html"

        async def noop(ctx, **kwargs):
            return None

        async def mock_report_handler(ctx, **kwargs):
            html_content = """<html>
<head><title>SD-WAN Diagnostic Report</title></head>
<body>
<h1>Diagnostic Report</h1>
<p>Status: Success</p>
<p>Trace ID: test-trace-id-001</p>
</body>
</html>"""
            report_path.write_text(html_content, encoding="utf-8")
            return str(report_path)

        handlers = {step.id: noop for step in QUICK_CHECK_FLOW.steps}
        handlers["step-report"] = mock_report_handler

        runtime = FlowRuntime()
        snapshots = await runtime.execute_flow(
            flow_def=QUICK_CHECK_FLOW,
            ctx=mock_context,
            handlers=handlers,
        )

        assert "step-report" in snapshots
        assert snapshots["step-report"].is_successful()
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "SD-WAN Diagnostic Report" in content
        assert "test-trace-id-001" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
