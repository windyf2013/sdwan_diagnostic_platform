import click

# 导入工具以触发装饰器注册
from sdwan_desktop.tools.implementations.system.windows import WindowsSystemTool
from sdwan_desktop.tools.implementations.network.dns import DnsTool
from sdwan_desktop.tools.implementations.network.tcping import TcpPortTool
from sdwan_desktop.tools.implementations.network.ping import PingTool
from sdwan_desktop.tools.implementations.network.traceroute import TraceRouteTool

@click.group()
def main():
    """SD-WAN 桌面诊断专家 - 命令行工具集"""
    pass

# 注册子命令
from sdwan_desktop.interface.cli.commands.quick_check import quick_check
from sdwan_desktop.interface.cli.commands.deep_dive import deep_dive
from sdwan_desktop.interface.cli.commands.waterfall import waterfall

main.add_command(quick_check)
main.add_command(deep_dive)
main.add_command(waterfall)

if __name__ == '__main__':
    main()
