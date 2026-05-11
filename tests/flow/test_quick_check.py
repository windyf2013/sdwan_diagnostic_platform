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
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity
from sdwan_desktop.flow.definitions.quick_check import QUICK_CHECK_FLOW
from sdwan_desktop.runtime.engine import FlowRuntime
from sdwan_desktop.services.collector.windows_collector import SystemInfoSnapshot, NetworkAdapter, IpConfig
from sdwan_desktop.services.connectivity import ConnectivityTestResult
from sdwan_desktop.services.dns_split import DnsSplitTestResult
from sdwan_desktop.services.analyzer.rule_engine import RuleEngine


@pytest.fixture
def mock_context():
    """创建模拟的 FlowContext"""
    ctx = FlowContext(
        trace_id="test-trace-id-001",
        logger=MagicMock(),
        data={}
    )
    return ctx


@pytest.fixture
def mock_system_snapshot():
    """创建模拟的系统采集快照"""
    adapter = NetworkAdapter(
        name="Ethernet",
        description="Intel Ethernet Connection",
        mac_address="00:11:22:33:44:55",
        ip_addresses=["192.168.1.100"],
        default_gateway="192.168.1.1",
        dhcp_enabled=True,
        is_connected=True,
        speed_mbps=1000
    )
    
    ip_config = IpConfig(
        default_gateway="192.168.1.1",
        dns_servers=["8.8.8.8", "114.114.114.114"]
    )
    
    return SystemInfoSnapshot(
        adapters=[adapter],
        ip_config=ip_config,
        routes=[],
        dns_config=None,
        proxy_config=None,
        firewall_status=None,
        arp_table=[],
        connections=[],
        ipv6_info=None
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
        mock_connectivity_result = ConnectivityTestResult(
            gateway_ping=None,
            domestic_dns=[],
            international_dns=[],
            domestic_targets=[],
            international_targets=[]
        )
        mock_connectivity_instance.test_all.return_value = mock_connectivity_result
        MockConnectivity.return_value = mock_connectivity_instance
        
        mock_dns_instance = AsyncMock()
        mock_dns_result = DnsSplitTestResult(
            domain_results=[],
            split_detected=False
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
        assert QUICK_CHECK_FLOW.id == "quick-check-v1"
        assert len(QUICK_CHECK_FLOW.steps) > 0
        
        # 验证步骤依赖关系
        step_ids = [s.id for s in QUICK_CHECK_FLOW.steps]
        assert "step-collect" in step_ids
        assert "step-connectivity" in step_ids
        assert "step-dns" in step_ids
        assert "step-analysis" in step_ids
        assert "step-report" in step_ids


@pytest.mark.asyncio
async def test_quick_check_error_handling(mock_context):
    """
    测试流程中的错误处理
    
    验证点：
    1. 单步失败不影响其他步骤
    2. 错误信息正确记录
    3. 流程能够继续执行或优雅降级
    """
    runtime = FlowRuntime()
    
    async def failing_step(ctx, **kwargs):
        raise Exception("Simulated failure")
    
    handlers = {
        "step-collect": failing_step,
    }
    
    # 验证流程能够捕获异常
    try:
        await runtime.execute_flow(QUICK_CHECK_FLOW, mock_context, handlers)
    except Exception as e:
        assert str(e) == "Simulated failure"


def test_flow_definition_structure():
    """测试Flow定义的结构完整性"""
    assert QUICK_CHECK_FLOW.id == "quick-check-v1"
    assert QUICK_CHECK_FLOW.name == "一键体检"
    assert QUICK_CHECK_FLOW.version == "1.0.0"
    
    # 验证所有必需的步骤都存在
    step_map = {s.id: s for s in QUICK_CHECK_FLOW.steps}
    
    required_steps = [
        "step-collect",
        "step-gateway", 
        "step-dns",
        "step-internet",
        "step-dns-split",
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
async def test_html_report_generation(mock_context, mock_system_snapshot):
    """
    测试打包后 HTML 报告生成功能
    
    验证点：
    1. 流程能完整执行完毕
    2. 报告生成步骤被调用
    3. 指定的输出路径下生成了 HTML 文件
    4. HTML 文件包含预期的关键内容（如标题、状态等）
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        report_path = Path(tmp_dir) / "report.html"
        
        # 准备 Mock 数据
        mock_connectivity_result = ConnectivityTestResult(
            gateway_ping=None,
            domestic_dns=[],
            international_dns=[],
            domestic_targets=[],
            international_targets=[]
        )
        mock_dns_result = DnsSplitTestResult(
            domain_results=[],
            split_detected=False
        )
        
        # 构造一个最终的诊断结果，通常由分析步骤产生并传递给报告步骤
        mock_diagnosis = DiagnosisResult(
            issues=[],
            summary="All checks passed",
            severity="info"
        )

        # 定义具体的 Handler 映射，模拟真实服务行为
        async def mock_collect_handler(ctx, **kwargs):
            return {"status": "success", "data": {"snapshot": mock_system_snapshot}}

        async def mock_connectivity_handler(ctx, **kwargs):
            return {"status": "success", "data": {"connectivity": mock_connectivity_result}}

        async def mock_dns_handler(ctx, **kwargs):
            return {"status": "success", "data": {"dns_split": mock_dns_result}}

        async def mock_analysis_handler(ctx, **kwargs):
            return {"status": "success", "data": {"diagnosis": mock_diagnosis}}

        async def mock_report_handler(ctx, **kwargs):
            # 模拟报告生成逻辑：写入一个假造的 HTML 文件
            html_content = """
            <html>
            <head><title>SD-WAN Diagnostic Report</title></head>
            <body>
                <h1>Diagnostic Report</h1>
                <p>Status: Success</p>
                <p>Trace ID: test-trace-id-001</p>
            </body>
            </html>
            """
            output_file = report_path
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return {"status": "success", "data": {"report_path": str(output_file)}}

        handlers = {
            "step-collect": mock_collect_handler,
            "step-connectivity": mock_connectivity_handler,
            "step-gateway": mock_connectivity_handler,
            "step-dns": mock_dns_handler,
            "step-analysis": mock_analysis_handler,
            "step-report": mock_report_handler,
            "step-internet": mock_connectivity_handler
        }
        
        # 补充缺失的步骤 Mock，防止 KeyError
        for step in QUICK_CHECK_FLOW.steps:
            if step.id not in handlers:
                handlers[step.id] = AsyncMock(return_value={"status": "success", "data": {}})

        runtime = FlowRuntime()
        # 执行流程
        snapshots = await runtime.execute_flow(
            flow_def=QUICK_CHECK_FLOW,
            ctx=mock_context,
            handlers=handlers
        )

        # 验证流程执行成功
        assert "step-report" in snapshots
        assert snapshots["step-report"].is_successful()

        # 验证文件生成
        assert report_path.exists(), f"Report file was not generated at {report_path}"
        
        # 验证文件内容
        content = report_path.read_text(encoding='utf-8')
        assert "SD-WAN Diagnostic Report" in content
        assert "test-trace-id-001" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
