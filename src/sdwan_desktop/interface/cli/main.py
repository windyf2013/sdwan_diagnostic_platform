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
from sdwan_desktop.interface.cli.commands.quick_check import (
    quick_check,
    dns_split_test,
    system_collect,
    gateway_test,
    dns_resolve,
    internet_test,
    cpe_link_test,
    rule_analyze,
    report_gen
)
from sdwan_desktop.interface.cli.commands.deep_dive import deep_dive
from sdwan_desktop.interface.cli.commands.waterfall import waterfall
from sdwan_desktop.interface.cli.commands.tcping_test import tcping_test

main.add_command(quick_check)
main.add_command(system_collect)
main.add_command(gateway_test)
main.add_command(dns_resolve)
main.add_command(internet_test)
main.add_command(dns_split_test)
main.add_command(cpe_link_test)
main.add_command(rule_analyze)
main.add_command(report_gen)
main.add_command(deep_dive)
main.add_command(waterfall)
main.add_command(tcping_test)

if __name__ == '__main__':
    main()
