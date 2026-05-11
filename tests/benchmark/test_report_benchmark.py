"""
性能基准测试 - 报告生成

验证报告生成的耗时和文件大小是否符合预期：
- 报告生成时间 < 5s
- 报告文件大小 < 5MB
"""

import pytest
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder


@pytest.mark.benchmark(group="report_generation")
def test_report_generation_time(perf_monitor):
    """
    测试报告生成耗时
    
    目标: < 5s (5000ms)
    """
    builder = HtmlReportBuilder()
    
    # 构造一个包含较多数据的诊断结果
    result = DiagnosisResult(
        diagnosis_type="quick_check",
        summary="Benchmark Test Summary",
        severity=Severity.WARNING,
        overall_confidence=0.85
    )
    
    perf_monitor.start()
    html_content = builder.build_quick_check_report(result)
    perf_monitor.stop()
    
    assert perf_monitor.duration_ms < 5000, f"Report generation took {perf_monitor.duration_ms:.2f}ms"
    assert len(html_content) > 0


@pytest.mark.benchmark(group="report_size")
def test_report_file_size(perf_monitor, tmp_path):
    """
    测试报告文件大小
    
    目标: < 5MB
    """
    builder = HtmlReportBuilder()
    
    result = DiagnosisResult(
        diagnosis_type="quick_check",
        summary="Size Benchmark Test",
        severity=Severity.INFO
    )
    
    output_path = tmp_path / "benchmark_report.html"
    
    perf_monitor.start()
    builder.build_quick_check_report(result, output_path=output_path)
    perf_monitor.stop()
    
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    assert file_size_mb < 5.0, f"Report file size is {file_size_mb:.2f}MB, exceeds 5MB limit"
