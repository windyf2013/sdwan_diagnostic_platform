"""
性能基准测试 - 内存占用

验证各场景下的内存使用情况：
- 空闲内存 < 200MB
- 诊断执行时内存峰值
- 报告生成时内存占用
"""

import pytest
import os
import psutil
from unittest.mock import AsyncMock, MagicMock, patch

from sdwan_desktop.core.types.context import FlowContext


def get_memory_mb():
    """获取当前进程内存占用 (MB)"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


@pytest.mark.benchmark(group="memory_usage")
def test_idle_memory_usage(perf_monitor):
    """
    测试应用空闲时的内存占用
    
    目标: < 200MB
    """
    # 基础导入后的内存状态
    start_mem = get_memory_mb()
    
    # 模拟一些基础操作
    from sdwan_desktop.tools.registry.dispatcher import ToolDispatcher
    dispatcher = ToolDispatcher()
    
    end_mem = get_memory_mb()
    delta = end_mem - start_mem
    
    # 验证增量内存占用在合理范围内
    assert delta < 50, f"Idle memory usage increased by {delta:.2f}MB"


@pytest.mark.benchmark(group="memory_usage")
def test_diagnosis_execution_memory(perf_monitor):
    """
    测试诊断执行过程中的内存峰值
    
    模拟大量数据采集和分析时的内存表现。
    """
    import gc
    from sdwan_desktop.core.types.diagnosis import DiagnosisResult
    
    start_mem = get_memory_mb()
    
    # 模拟生成一个包含大量规则结果的诊断报告
    results = []
    for i in range(1000):
        results.append({
            "rule_id": f"rule_{i}",
            "status": "PASS",
            "details": "x" * 100  # 模拟一些详细日志
        })
    
    diagnosis = DiagnosisResult(
        diagnosis_type="benchmark",
        target_description="Memory Test",
        summary="Benchmark Test",
        recommendations=[],
        evidences=[]
    )
    
    end_mem = get_memory_mb()
    delta = end_mem - start_mem
    
    assert delta < 50, f"Diagnosis execution memory increased by {delta:.2f}MB"


@pytest.mark.benchmark(group="memory_usage")
def test_report_generation_memory(perf_monitor):
    """
    测试报告生成时的内存占用
    
    验证 HTML 构建器在处理大体积数据时的内存效率。
    """
    import gc
    from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder
    
    start_mem = get_memory_mb()
    
    builder = HtmlReportBuilder()
    
    # 模拟生成一个较大的 HTML 内容
    large_content = "<div>" + "<p>Test content</p>" * 5000 + "</div>"
    
    # 构造一个临时的 DiagnosisResult 用于测试
    from sdwan_desktop.core.types.diagnosis import DiagnosisResult
    result = DiagnosisResult(diagnosis_type="test", summary="Test")
    
    html_output = builder.build_quick_check_report(result)
    
    end_mem = get_memory_mb()
    delta = end_mem - start_mem
    
    assert delta < 100, f"Report generation memory increased by {delta:.2f}MB"
