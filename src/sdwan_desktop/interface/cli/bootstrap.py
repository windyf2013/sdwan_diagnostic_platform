"""CLI 共享引导：核心子命令注册与 PyInstaller 隐藏依赖（不含 Playwright / waterfall）。"""

from __future__ import annotations

import os
import sys

import click

from sdwan_desktop.tools.implementations.system.windows import WindowsSystemTool  # noqa: F401
from sdwan_desktop.tools.implementations.network.dns import DnsTool  # noqa: F401
from sdwan_desktop.tools.implementations.network.tcping import TcpPortTool  # noqa: F401
from sdwan_desktop.tools.implementations.network.ping import PingTool  # noqa: F401
from sdwan_desktop.tools.implementations.network.traceroute import TraceRouteTool  # noqa: F401

from sdwan_desktop.interface.cli.commands.quick_check import (
    quick_check,
    dns_split_test,
    system_collect,
    gateway_test,
    dns_resolve,
    internet_test,
    cpe_link_test,
    rule_analyze,
    report_gen,
)
from sdwan_desktop.interface.cli.commands.deep_dive import deep_dive
from sdwan_desktop.interface.cli.commands.business_diagnose import business_diagnose
from sdwan_desktop.interface.cli.commands.tcping_test import tcping_test

# PyInstaller：显式导入三条功能流与 CPE 解析器，避免 collect 遗漏
import sdwan_desktop.flow.definitions.quick_check  # noqa: F401
import sdwan_desktop.flow.definitions.deep_dive  # noqa: F401
import sdwan_desktop.flow.definitions.business_diagnose  # noqa: F401
import sdwan_desktop.flow.handlers.quick_check_steps  # noqa: F401
import sdwan_desktop.flow.handlers.deep_dive_steps  # noqa: F401
import sdwan_desktop.services.parser.vendor.cisco_sdwan  # noqa: F401
import sdwan_desktop.services.parser.vendor.raisecom_msg5200  # noqa: F401
import sdwan_desktop.services.parser.vendor.raisecom_msg5200b  # noqa: F401

CLI_MODULE_FULL = "sdwan_desktop.interface.cli.main"
CLI_MODULE_CORE = "sdwan_desktop.interface.cli.main_core"


def ensure_frozen_import_paths() -> None:
    """PyInstaller 打包后保证 src 布局可导入。"""
    if not getattr(sys, "frozen", False):
        return
    app_dir = os.path.dirname(sys.executable)
    for path in (app_dir, os.path.join(app_dir, "src")):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


def create_cli_group() -> click.Group:
    """创建 Click 根命令组。"""
    @click.group()
    def cli() -> None:
        """SD-WAN 桌面诊断专家 - 命令行工具集"""

    return cli


def register_core_commands(cli: click.Group) -> None:
    """注册不含 waterfall 的核心子命令。"""
    cli.add_command(quick_check)
    cli.add_command(system_collect)
    cli.add_command(gateway_test)
    cli.add_command(dns_resolve)
    cli.add_command(internet_test)
    cli.add_command(dns_split_test)
    cli.add_command(cpe_link_test)
    cli.add_command(rule_analyze)
    cli.add_command(report_gen)
    cli.add_command(deep_dive)
    cli.add_command(business_diagnose)
    cli.add_command(tcping_test)


def build_core_cli() -> click.Group:
    """核心版 CLI：一键体检 / 深度诊断 / 业务路径诊断等，无 Playwright。"""
    ensure_frozen_import_paths()
    cli = create_cli_group()
    register_core_commands(cli)
    return cli
