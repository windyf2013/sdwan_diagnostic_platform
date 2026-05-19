"""cli_runner：Click 版本兼容 + sys.exit 与真异常的语义区分。"""

import sys

import click

from sdwan_desktop.interface.gui.cli_runner import (
    _click_result_to_cli_run_result,
    _make_cli_runner,
)


def test_make_cli_runner_instantiates() -> None:
    runner = _make_cli_runner()
    assert runner is not None


def test_result_conversion_preserves_stdout_on_sys_exit() -> None:
    """CLI 主动 ``sys.exit(N)`` 时只回传退出码，不应把 stdout 里的根因覆写成 "SystemExit: N"。"""

    @click.command()
    def fake_cmd() -> None:
        click.echo("执行失败: CPE 连接超时")
        sys.exit(1)

    runner = _make_cli_runner()
    raw = runner.invoke(fake_cmd, [], prog_name="agentctl", catch_exceptions=True)
    assert isinstance(raw.exception, SystemExit)

    result = _click_result_to_cli_run_result(raw)
    assert result.returncode == 1
    assert "执行失败: CPE 连接超时" in result.stdout
    assert "SystemExit" not in result.stderr


def test_result_conversion_reports_real_exception() -> None:
    """非 ``SystemExit`` 的异常仍按真实失败上报，避免静默掩盖编程错误。"""

    @click.command()
    def boom_cmd() -> None:
        raise RuntimeError("boom")

    runner = _make_cli_runner()
    raw = runner.invoke(boom_cmd, [], prog_name="agentctl", catch_exceptions=True)
    assert isinstance(raw.exception, RuntimeError)

    result = _click_result_to_cli_run_result(raw)
    assert result.returncode == 1
    assert "RuntimeError: boom" in result.stderr
