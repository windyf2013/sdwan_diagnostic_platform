"""
Waterfall 诊断 CLI 命令

提供命令行入口，执行完整的 Web 性能分析流程。
"""

import asyncio
import click
import logging
import os
from datetime import datetime

from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext
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
@click.option("--timeout", default=90, help="采集超时时间（秒，默认 90）")
@click.option("--output", "-o", default=None, help="报告输出路径")
@click.option(
    "--proxy",
    default=None,
    metavar="URL",
    help="HTTP 代理（如 http://127.0.0.1:7890）；为空时按 HTTPS_PROXY/HTTP_PROXY 环境变量回退",
)
@click.option(
    "--wait-until",
    type=click.Choice(["load", "domcontentloaded", "networkidle"]),
    default="load",
    help="导航等待事件（默认 load；门户站常驻轮询会让 networkidle 整体超时）",
)
def waterfall(url: str, headless: bool, timeout: int, output: str, proxy: str, wait_until: str):
    """执行 Web 性能瀑布流分析

    Args:
        url: 目标页面 URL
        headless: 是否隐藏浏览器窗口
        timeout: 超时时间
        output: 报告保存路径
        proxy: HTTP 代理 URL（可选）
        wait_until: Playwright 导航等待事件
    """
    print(f"[START] 开始对 {url} 进行性能分析...")

    # 在事件循环中运行异步代码
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # 1. HAR 采集
        har_tool = HarCaptureTool()

        # 构造 ToolRequest 和 FlowContext
        params: dict = {
            "url": url,
            "headless": headless,
            "timeout": timeout * 1000,  # 转换为毫秒
            "wait_until": wait_until,
        }
        if proxy:
            params["proxy"] = proxy
        request = ToolRequest(
            tool_name="har_capture",
            parameters=params,
        )
        ctx = FlowContext(flow_id="cli-waterfall", flow_name="cli-waterfall-diagnosis")
        
        # 异步执行 HAR 采集
        har_result = loop.run_until_complete(har_tool.execute(request, ctx))
        
        # 检查执行结果
        if not har_result or not har_result.success:
            error_msg = har_result.error_message if har_result else "未知错误"
            print(f"[ERROR] HAR 采集失败: {error_msg}")
            return
        
        har_path = har_result.data.get("har_file_path") if har_result.data else None
        
        if not har_path or not os.path.exists(har_path):
            print(f"[ERROR] HAR 文件不存在: {har_path}")
            return

        print(f"[OK] HAR 文件已保存: {har_path}")
        
        # 2. HAR 解析
        parser = HarParser()
        waterfall_result = parser.parse(har_path, target_url=url)
        print(f"[OK] 解析完成: {waterfall_result.total_requests} 个资源, 总耗时 {waterfall_result.page_load_time:.0f}ms")
        
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
            print(f"[WARN] 发现 {len(all_issues)} 个性能问题")
        else:
            print(f"[OK] 未发现明显性能瓶颈")
            
        # 4. 生成报告
        generator = ReportGenerator()
        if not output:
            output = f"waterfall_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        html_content = generator.generate_waterfall_report(waterfall_result, all_issues, output)
        print(f"[REPORT] 报告已生成: {os.path.abspath(output)}")
        
    finally:
        loop.close()


if __name__ == "__main__":
    waterfall()
