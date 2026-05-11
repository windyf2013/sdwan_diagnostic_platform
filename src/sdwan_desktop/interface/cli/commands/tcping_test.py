"""
TCP端口探测工具 - 独立CLI测试命令

遵循 SDWAN_SPEC.md §2.4 工具系统规范
遵循 CLI模块独立测试设计规范
确保与GUI调用流程完全一致
"""

import asyncio
import click
from datetime import datetime
from typing import Optional

from sdwan_desktop.tools.registry import tool_registry
from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext


@click.command(name="tcping")
@click.argument("host", type=str)
@click.option("--port", "-p", type=int, default=80, help="目标端口（默认80）")
@click.option("--count", "-c", type=int, default=4, help="探测次数（默认4）")
@click.option("--timeout", "-t", type=int, default=5, help="超时秒数（默认5）")
@click.option("--source-ip", type=str, default=None, help="源IP地址（可选）")
@click.option("--source-port", type=int, default=None, help="源端口（可选）")
@click.option("--verbose", "-v", is_flag=True, help="显示详细输出")
def tcping_test(
    host: str,
    port: int,
    count: int,
    timeout: int,
    source_ip: Optional[str],
    source_port: Optional[int],
    verbose: bool,
):
    """TCP端口连通性测试
    
    通过TCP三次握手测试目标主机端口的连通性，测量响应时间和丢包率。
    
    Args:
        host: 目标主机IP或域名
        port: 目标端口（1-65535）
        count: 探测次数（1-10）
        timeout: 超时秒数（1-30）
        source_ip: 源IP地址（可选）
        source_port: 源端口（可选）
        verbose: 显示详细输出
    
    Examples:
        # 基本用法
        agentctl tcping www.github.com --port 443
        
        # 自定义参数
        agentctl tcping 192.168.1.1 --port 80 --count 10 --timeout 3
        
        # 详细模式
        agentctl tcping www.baidu.com --port 443 --verbose
    """
    # 参数校验
    if port < 1 or port > 65535:
        click.echo(f"❌ 错误: 端口必须在1-65535范围内，当前值: {port}")
        return
    
    if count < 1 or count > 10:
        click.echo(f"❌ 错误: 探测次数必须在1-10范围内，当前值: {count}")
        return
    
    if timeout < 1 or timeout > 30:
        click.echo(f"❌ 错误: 超时必须在1-30秒范围内，当前值: {timeout}")
        return
    
    # 构建参数（与GUI保持一致）
    params = {
        "host": host,
        "port": port,
        "count": count,
        "timeout": timeout,
    }
    
    if source_ip:
        params["source_ip"] = source_ip
    
    if source_port:
        params["source_port"] = source_port
    
    # 显示执行信息
    click.echo(f"\n{'='*60}")
    click.echo(f"🔍 TCP端口探测测试")
    click.echo(f"{'='*60}")
    click.echo(f"目标主机: {host}")
    click.echo(f"目标端口: {port}")
    click.echo(f"探测次数: {count}")
    click.echo(f"超时时间: {timeout}秒")
    if source_ip:
        click.echo(f"源IP地址: {source_ip}")
    if source_port:
        click.echo(f"源端口: {source_port}")
    click.echo(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    click.echo(f"{'='*60}\n")
    
    # 执行测试（与GUI ToolWorker.run完全一致的流程）
    try:
        # 1. 从tool_registry获取工具类
        tool_class = tool_registry.get_tool("tcping")
        if not tool_class:
            raise Exception("Tool tcping not found")
        
        # 2. 创建ToolRequest
        request = ToolRequest(
            tool_name="tcping",
            parameters=params
        )
        
        # 3. 创建FlowContext
        ctx = FlowContext(
            flow_id="cli-tcping-test",
            flow_name="cli-tcping-execution"
        )
        
        # 4. 在异步事件中运行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 5. 实例化工具并执行
            tool_instance = tool_class()
            result = loop.run_until_complete(tool_instance.execute(request, ctx))
            
            # 6. 转换为JSON字典（与GUI一致）
            result_dict = result.to_json_dict()
            
        finally:
            loop.close()
        
        # 显示结果
        _display_result(result_dict, verbose)
        
    except Exception as e:
        click.echo(f"\n{'='*60}")
        click.echo(f"❌ 执行失败")
        click.echo(f"{'='*60}")
        click.echo(f"错误: {str(e)}")
        if verbose:
            import traceback
            traceback.print_exc()
        click.echo(f"{'='*60}\n")


def _display_result(result_dict: dict, verbose: bool = False):
    """格式化显示测试结果
    
    Args:
        result_dict: 工具执行结果的JSON字典
        verbose: 是否显示详细信息
    """
    click.echo(f"\n{'='*60}")
    
    if result_dict.get("success"):
        click.echo(f"✅ 执行成功")
    else:
        click.echo(f"❌ 执行失败")
        if result_dict.get("error_message"):
            click.echo(f"错误信息: {result_dict['error_message']}")
        if result_dict.get("error_code"):
            click.echo(f"错误代码: {result_dict['error_code']}")
        click.echo(f"{'='*60}\n")
        return
    
    click.echo(f"{'='*60}\n")
    
    # 显示耗时
    if "duration_ms" in result_dict:
        click.echo(f"⏱️  耗时: {result_dict['duration_ms']:.2f} ms\n")
    
    # 显示详细数据
    data = result_dict.get("data", {})
    if not data:
        click.echo("⚠️  无返回数据\n")
        return
    
    # 基本信息
    click.echo(f"📌 目标主机: {data.get('host', 'N/A')}")
    click.echo(f"📌 目标端口: {data.get('port', 'N/A')}")
    click.echo(f"📌 解析IP: {data.get('resolved_ip', 'N/A')}")
    click.echo(f"📌 端口状态: {'✅ 开放' if data.get('port_open') else '❌ 关闭'}\n")
    
    # 统计信息
    click.echo(f"📊 探测统计:")
    click.echo(f"   - 总探测次数: {data.get('total_probes', 0)}")
    click.echo(f"   - 成功次数: {data.get('successful_probes', 0)}")
    click.echo(f"   - 丢包率: {data.get('loss_rate', 0) * 100:.1f}%\n")
    
    # 响应时间统计
    if data.get("response_time_avg") is not None:
        click.echo(f"⏱️  响应时间:")
        click.echo(f"   - 最小: {data.get('response_time_min', 0):.2f} ms")
        click.echo(f"   - 平均: {data.get('response_time_avg', 0):.2f} ms")
        click.echo(f"   - 最大: {data.get('response_time_max', 0):.2f} ms")
        if data.get("response_time_stddev") is not None:
            click.echo(f"   - 标准差: {data.get('response_time_stddev', 0):.2f} ms\n")
    
    # 每次探测的详细结果（verbose模式）
    if verbose and data.get("response_times"):
        click.echo(f"📋 详细探测记录:")
        for i, rtt in enumerate(data["response_times"], 1):
            status = "✅" if rtt is not None else "❌"
            rtt_str = f"{rtt:.2f} ms" if rtt is not None else "超时"
            click.echo(f"   {i}. {status} {rtt_str}")
        click.echo()
    
    # Banner信息（如果获取到）
    if data.get("banner"):
        click.echo(f"🎯 服务Banner:")
        click.echo(f"   {data['banner']}\n")
    
    click.echo(f"{'='*60}\n")


# 注册到主命令组
if __name__ == "__main__":
    tcping_test()
