"""核心版 / 完整版 CLI 入口分离：core 不拉 Playwright / waterfall。"""

from __future__ import annotations

import importlib
import sys

import pytest

from sdwan_desktop.interface.cli.bootstrap import CLI_MODULE_CORE, CLI_MODULE_FULL
from sdwan_desktop.interface.gui import cli_runner


@pytest.fixture(autouse=True)
def _restore_cli_profile():
    previous = cli_runner._cli_profile
    yield
    cli_runner.configure_gui_cli_profile(previous)


def test_main_core_import_does_not_load_playwright() -> None:
    had_playwright = "playwright" in sys.modules
    for name in (
        CLI_MODULE_CORE,
        CLI_MODULE_FULL,
        "sdwan_desktop.interface.cli.bootstrap",
    ):
        sys.modules.pop(name, None)

    importlib.import_module(CLI_MODULE_CORE)

    if not had_playwright:
        assert "playwright" not in sys.modules


def test_main_full_registers_waterfall_command() -> None:
    for name in (CLI_MODULE_FULL, CLI_MODULE_CORE):
        sys.modules.pop(name, None)

    full = importlib.import_module(CLI_MODULE_FULL)
    assert "waterfall" in full.main.commands


def test_main_core_has_no_waterfall_command() -> None:
    for name in (CLI_MODULE_FULL, CLI_MODULE_CORE):
        sys.modules.pop(name, None)

    core = importlib.import_module(CLI_MODULE_CORE)
    assert "waterfall" not in core.main.commands


def test_argv_for_subprocess_uses_core_module() -> None:
    cli_runner.configure_gui_cli_profile(cli_runner.PROFILE_CORE)
    argv = cli_runner._argv_for_subprocess(["business-diagnose", "-o", "out.html"])
    assert argv[1:3] == ["-m", CLI_MODULE_CORE]


def test_argv_for_subprocess_uses_full_module_by_default() -> None:
    cli_runner.configure_gui_cli_profile(cli_runner.PROFILE_FULL)
    argv = cli_runner._argv_for_subprocess(["quick-check"])
    assert argv[1:3] == ["-m", CLI_MODULE_FULL]


def test_parse_cli_step_progress() -> None:
    from sdwan_desktop.interface.gui.cli_runner import parse_cli_step_progress

    parsed = parse_cli_step_progress("[5/8] 拓扑后主动探测...")
    assert parsed == (62, "[5/8] 拓扑后主动探测...")


def test_parse_cli_step_progress_inline_ok() -> None:
    from sdwan_desktop.interface.gui.cli_runner import parse_cli_step_progress

    parsed = parse_cli_step_progress("[1/8] 采集 PC 端系统信息... OK")
    assert parsed is not None
    assert parsed[0] == 12


def test_resolve_agentctl_command_dev_uses_python_module() -> None:
    from sdwan_desktop.interface.gui.cli_runner import (
        CLI_MODULE_CORE,
        resolve_agentctl_command,
    )

    cli_runner.configure_gui_cli_profile(cli_runner.PROFILE_CORE)
    cmd = resolve_agentctl_command(["deep-dive", "-o", "out.html"])
    assert cmd[0] == sys.executable or cmd[0].endswith("python.exe")
    assert "-m" in cmd
    assert CLI_MODULE_CORE in cmd
    assert "deep-dive" in cmd
