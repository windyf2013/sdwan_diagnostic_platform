"""
Waterfall 端到端集成测试

验证从 HAR 采集到报告生成的完整流程。
"""

import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch

from sdwan_desktop.core.types.waterfall import WaterfallResult, ResourceTiming
from sdwan_desktop.services.parser.har_parser import HarParser
from sdwan_desktop.services.analyzer.rules.performance import (
    check_page_load_time,
    check_render_blocking,
)
from sdwan_desktop.services.reporter.report_generator import ReportGenerator


def test_integration_waterfall_workflow():
    """模拟完整的 Waterfall 分析工作流"""
    
    # 1. 模拟 HAR 解析结果
    resources = [
        ResourceTiming(
            url="https://example.com/style.css",
            dns_time=50.0,
            connect_time=100.0,
            ssl_time=150.0,
            wait_time=200.0,
            download_time=300.0,
            total_time=800.0,
            is_render_blocking=True
        ),
        ResourceTiming(
            url="https://example.com/app.js",
            dns_time=40.0,
            connect_time=90.0,
            ssl_time=140.0,
            wait_time=180.0,
            download_time=250.0,
            total_time=700.0,
            is_render_blocking=True
        )
    ]
    
    waterfall = WaterfallResult(target_url="https://example.com", resources=resources)
    waterfall.calculate_stats()
    
    # 2. 执行性能规则检查
    issues = []
    issues.extend(check_page_load_time(waterfall))
    issues.extend(check_render_blocking(waterfall))
    
    assert len(issues) >= 1
    
    # 3. 生成 HTML 报告
    generator = ReportGenerator()
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.html') as f:
        output_path = f.name
        
    try:
        html_content = generator.generate_waterfall_report(waterfall, issues, output_path)
        
        assert os.path.exists(output_path)
        assert "Web性能瀑布流分析报告" in html_content
        assert "https://example.com" in html_content
        assert "PERF-007" in html_content  # 渲染阻塞规则 ID
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


def test_waterfall_report_content():
    """验证报告内容的完整性"""
    resources = [
        ResourceTiming(url="https://test.com/img.png", total_time=100.0)
    ]
    waterfall = WaterfallResult(target_url="https://test.com", resources=resources)
    waterfall.calculate_stats()
    
    generator = ReportGenerator()
    html = generator.generate_waterfall_report(waterfall, [])
    
    # 验证关键 HTML 元素是否存在
    assert '<div class="stat-value">' in html
    assert '<div class="resource-name"' in html
    assert 'https://test.com/img.png' in html
