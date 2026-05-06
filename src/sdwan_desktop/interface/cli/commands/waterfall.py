"""
Waterfall 诊断 CLI 命令

提供命令行入口，执行完整的 Web 性能分析流程。
"""

import click
import logging
import os
from datetime import datetime

from sdwan_desktop.tools.implementations.web.har_capture import HarCaptureTool
from sdwan_desktop.services.parser.har_parser import HarParser
from sdwan_desktop.services.analyzer.perf_analyzer import PerfAnalyzer
from sdwan_desktop.services.analyzer.rules.performance import (
    check_page_load_time,
    check_dns_performance,
    check_tcp_connect_performance,
    check_ssl_handshake_performance,
    check_ttfb_performance,
    check_download_performance,
    check_render_blocking,
)
from sdwan_desktop.services.reporter.report_generator import ReportGenerator

logger = logging.getLogger(__name__)


@click.command()
@click.argument("url")
@click.option("--headless/--no-headless", default=True, help="是否使用无头模式运行浏览器")
@click.option("--timeout", default=60, help="采集超时时间（秒）")
@click.option("--output", "-o", default=None, help="报告输出路径")
def waterfall(url: str, headless: bool, timeout: int, output: str):
    """执行 Web 性能瀑布流分析
    
    Args:
        url: 目标页面 URL
        headless: 是否隐藏浏览器窗口
        timeout: 超时时间
        output: 报告保存路径
    """
    print(f"🚀 开始对 {url} 进行性能分析...")
    
    # 1. HAR 采集
    har_tool = HarCaptureTool()
    har_result = har_tool.execute(url=url, headless=headless, timeout=timeout)
    har_path = har_result.data.get("har_file_path")
    
    if not har_path or not os.path.exists(har_path):
        print("❌ HAR 采集失败")
        return

    print(f"✅ HAR 文件已保存: {har_path}")
    
    # 2. HAR 解析
    parser = HarParser()
    waterfall_result = parser.parse(har_path)
    print(f"✅ 解析完成: {waterfall_result.total_requests} 个资源, 总耗时 {waterfall_result.page_load_time:.0f}ms")
    
    # 3. 性能规则匹配
    all_issues = []
    all_issues.extend(check_page_load_time(waterfall_result))
    all_issues.extend(check_dns_performance(waterfall_result))
    all_issues.extend(check_tcp_connect_performance(waterfall_result))
    all_issues.extend(check_ssl_handshake_performance(waterfall_result))
    all_issues.extend(check_ttfb_performance(waterfall_result))
    all_issues.extend(check_download_performance(waterfall_result))
    all_issues.extend(check_render_blocking(waterfall_result))
    
    if all_issues:
        print(f"⚠️ 发现 {len(all_issues)} 个性能问题")
    else:
        print("✨ 未发现明显性能瓶颈")
        
    # 4. 生成报告
    generator = ReportGenerator()
    if not output:
        output = f"waterfall_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    
    html_content = generator.generate_waterfall_report(waterfall_result, all_issues, output)
    print(f"📄 报告已生成: {os.path.abspath(output)}")


if __name__ == "__main__":
    waterfall()
