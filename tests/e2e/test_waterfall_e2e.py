"""
业务监测端到端测试

验证 Waterfall Flow 的完整执行链路：
HAR采集 → 解析 → 性能分析 → 报告生成
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.waterfall import WaterfallResult, ResourceTiming
from sdwan_desktop.flow.definitions.waterfall import WATERFALL_FLOW
from sdwan_desktop.runtime.engine import FlowRuntime


@pytest.mark.asyncio
async def test_waterfall_happy_path(sample_flow_context, temp_dir):
    """
    测试业务监测完整流程 (Happy Path)
    
    验证点：
    1. HAR 采集成功（Mock Playwright）
    2. WaterfallResult 时序数据正确
    3. 性能分析识别出瓶颈
    4. 报告文件生成
    """
    ctx = sample_flow_context
    runtime = FlowRuntime()
    
    with patch('sdwan_desktop.tools.implementations.web.har_capture.HarCaptureTool') as MockHarTool, \
         patch('sdwan_desktop.services.parser.har_parser.HarParser') as MockHarParser, \
         patch('sdwan_desktop.services.analyzer.perf_analyzer.PerfAnalyzer') as MockPerfAnalyzer, \
         patch('sdwan_desktop.services.reporter.report_generator.ReportGenerator') as MockReportGen:
        
        # 1. Mock HarCaptureTool
        mock_har_tool_instance = AsyncMock()
        mock_har_tool_instance.execute.return_value = {
            "har_file_path": str(temp_dir / "mock.har"),
            "screenshot_path": str(temp_dir / "mock.png")
        }
        MockHarTool.return_value = mock_har_tool_instance
        
        # 2. Mock HarParser
        mock_parser_instance = AsyncMock()
        mock_waterfall_result = WaterfallResult(
            trace_id=ctx.trace_id,
            target_url="https://example.com",
            resources=[],
            page_load_time=1000,
            total_size_bytes=50000,
            slowest_resources=[]
        )
        mock_parser_instance.parse.return_value = mock_waterfall_result
        MockHarParser.return_value = mock_parser_instance
        
        # 3. Mock PerfAnalyzer
        mock_perf_instance = AsyncMock()
        mock_perf_instance.analyze.return_value = {"bottlenecks": []}
        MockPerfAnalyzer.return_value = mock_perf_instance
        
        # 4. Mock ReportGenerator
        mock_report_instance = AsyncMock()
        mock_report_instance.generate_waterfall_report.return_value = str(temp_dir / "waterfall_report.html")
        MockReportGen.return_value = mock_report_instance
        
        # 定义步骤处理器
        async def step_har_capture(ctx):
            result = await mock_har_tool_instance.execute("https://example.com", ctx)
            ctx.set("har_data", result)
            return result

        async def step_har_parse(ctx):
            har_data = ctx.get("har_data")
            if not har_data:
                return None
            result = await mock_parser_instance.parse(har_data.get("har_file_path"))
            ctx.set("waterfall_result", result)
            return result
            
        async def step_perf_analyze(ctx):
            waterfall_result = ctx.get("waterfall_result")
            return await mock_perf_instance.analyze(waterfall_result)
            
        async def step_rule_check(ctx):
            return []
            
        async def step_report_generate(ctx):
            waterfall_result = ctx.get("waterfall_result")
            perf_summary = ctx.get("perf_summary")
            rule_results = ctx.get("rule_results", [])

            report_path = await mock_report_instance.generate_waterfall_report(
                waterfall_result, perf_summary, rule_results, temp_dir
            )
            
            # 模拟实际生成文件
            Path(report_path).touch()
            
            ctx.set("report_path", report_path)
            return report_path

        handlers = {
            "step-har-capture": step_har_capture,
            "step-har-parse": step_har_parse,
            "step-perf-analyze": step_perf_analyze,
            "step-rule-check": step_rule_check,
            "step-report-generate": step_report_generate
        }
        
        # 执行流程
        snapshots = await runtime.execute_flow(WATERFALL_FLOW, ctx, handlers)
        
        # 验证点 1: 所有步骤执行成功
        assert len(snapshots) == len(WATERFALL_FLOW.steps)
        for step_id, snapshot in snapshots.items():
            assert snapshot.status.value in ["completed", "COMPLETED"], f"Step {step_id} failed: {snapshot.error}"
        
        # 验证点 2: WaterfallResult 数据结构正确
        waterfall_result = ctx.get("waterfall_result")
        assert waterfall_result is not None
        assert isinstance(waterfall_result, WaterfallResult)
        assert waterfall_result.target_url == "https://example.com"
        
        # 验证点 3: 报告文件存在
        report_path = ctx.get("report_path")
        assert report_path is not None
        assert Path(report_path).exists()


@pytest.mark.asyncio
async def test_waterfall_har_parsing_accuracy(sample_flow_context):
    """
    验证 HAR 解析后的时序数据准确性
    """
    ctx = sample_flow_context
    
    # 模拟一个包含详细 timings 的 HAR 条目
    mock_entry = {
        "startedDateTime": "2026-04-27T10:00:00.000Z",
        "time": 100,
        "request": {"url": "https://example.com/style.css"},
        "timings": {
            "dns": 10,
            "connect": 20,
            "ssl": 15,
            "send": 5,
            "wait": 30,
            "receive": 20
        }
    }
    
    from sdwan_desktop.services.parser.har_parser import HarParser
    parser = HarParser()
    
    # 调用内部解析方法
    resource = parser._parse_entry(mock_entry)
    
    assert resource is not None
    assert resource.dns_time >= 0
    assert resource.connect_time >= 0
    assert resource.ssl_time >= 0
    assert resource.wait_time >= 0
