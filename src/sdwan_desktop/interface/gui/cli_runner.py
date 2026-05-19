"""GUI 内调用 agentctl 子命令：优先隐藏子进程（可实时进度），打包环境用同目录 agentctl*.exe。"""

from __future__ import annotations

import importlib
import logging
import re
import subprocess
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Sequence

from sdwan_desktop.interface.cli.bootstrap import CLI_MODULE_CORE, CLI_MODULE_FULL

logger = logging.getLogger(__name__)

PROFILE_FULL = "full"
PROFILE_CORE = "core"

_cli_profile: str = PROFILE_FULL

_STEP_PROGRESS_RE = re.compile(r"^\[(\d+)/(\d+)\]\s*(.*)$")
_STEP_TAG_SCAN_RE = re.compile(r"\[(\d+)/(\d+)\][^\n\r]*")

# deep-dive 最坏步预算约 300+180s + 余量；避免 GUI 子进程无限挂起。
_DEFAULT_AGENTCTL_SUBPROCESS_TIMEOUT_S = 660.0


def configure_gui_cli_profile(profile: str) -> None:
    """按 GUI 版本选择 CLI 入口（core 不加载 Playwright / waterfall）。"""
    global _cli_profile
    _cli_profile = profile if profile in (PROFILE_FULL, PROFILE_CORE) else PROFILE_FULL


def _cli_module() -> str:
    return CLI_MODULE_CORE if _cli_profile == PROFILE_CORE else CLI_MODULE_FULL


def _cli_prog_name() -> str:
    return "agentctl-core" if _cli_profile == PROFILE_CORE else "agentctl"


def _strip_cli_module_prefix(args: list[str]) -> list[str]:
    """去掉 ``-m <module>`` 前缀（兼容 full / core 两种模块名）。"""
    if len(args) >= 2 and args[0] == "-m" and args[1] in (CLI_MODULE_FULL, CLI_MODULE_CORE):
        return args[2:]
    return args


def _normalize_subcommand_argv(argv: Sequence[str]) -> List[str]:
    """得到以子命令名开头的参数列表（如 ``deep-dive``, ``-o``, ...）。"""
    args = list(argv)
    if args and args[0] in ("agentctl", "agentctl-core", "python", sys.executable):
        args = args[1:]
    return _strip_cli_module_prefix(args)


def sibling_agentctl_executable() -> Optional[Path]:
    """打包 GUI 同目录下的 agentctl 可执行文件（build_core / build_full 与 GUI 并列分发）。"""
    if not getattr(sys, "frozen", False):
        return None
    install_dir = Path(sys.executable).resolve().parent
    primary = (
        "agentctl-core.exe"
        if _cli_profile == PROFILE_CORE
        else "agentctl.exe"
    )
    for file_name in (primary, "agentctl.exe", "agentctl-core.exe"):
        candidate = install_dir / file_name
        if candidate.is_file():
            return candidate
    return None


def resolve_agentctl_command(argv: Sequence[str]) -> List[str]:
    """构造用于 ``Popen`` 的命令行：打包优先 ``agentctl*.exe``，开发环境走 ``python -m``。"""
    sub_args = _normalize_subcommand_argv(argv)
    bundled = sibling_agentctl_executable()
    if bundled is not None:
        return [str(bundled), *sub_args]
    return _argv_for_subprocess(argv)


def parse_cli_step_progress(line: str) -> Optional[tuple[int, str]]:
    """解析 CLI 步骤行 ``[n/total] …``，返回 ``(percent, status_text)``。"""
    text = (line or "").strip()
    if not text:
        return None
    match = _STEP_PROGRESS_RE.match(text)
    if not match:
        scan = _STEP_TAG_SCAN_RE.search(text)
        if not scan:
            return None
        step_no = int(scan.group(1))
        total = int(scan.group(2))
        detail = text[scan.end() :].strip() if scan else ""
    else:
        step_no = int(match.group(1))
        total = int(match.group(2))
        detail = (match.group(3) or "").strip()
    if total <= 0:
        return None
    pct = max(1, min(99, int(100 * step_no / total)))
    label = f"[{step_no}/{total}]"
    if detail:
        label = f"{label} {detail}"
    return pct, label


@dataclass(frozen=True)
class CliRunResult:
    """与 ``subprocess.CompletedProcess`` 对齐的 CLI 执行结果。"""

    returncode: int
    stdout: str
    stderr: str


def _argv_for_subprocess(argv: Sequence[str]) -> List[str]:
    """将 ``[agentctl, business-diagnose, ...]`` 转为子进程参数列表。"""
    module = _cli_module()
    sub_args = _normalize_subcommand_argv(argv)
    return [sys.executable, "-m", module, *sub_args]


def _make_cli_runner():
    """兼容旧版 Click（无 ``mix_stderr`` 参数）。"""
    import inspect

    from click.testing import CliRunner

    kwargs: dict = {}
    if "mix_stderr" in inspect.signature(CliRunner.__init__).parameters:
        kwargs["mix_stderr"] = False
    return CliRunner(**kwargs)


def _click_result_to_cli_run_result(result) -> CliRunResult:
    """把 ``click.testing.Result`` 转换为 ``CliRunResult``。"""
    out = result.output or ""
    err_text = ""
    try:
        err_text = getattr(result, "stderr", "") or ""
    except (ValueError, AttributeError):
        err_text = ""

    exc = result.exception
    if exc is not None and not isinstance(exc, SystemExit):
        logger.exception("agentctl 进程内调用失败")
        suffix = f"{type(exc).__name__}: {exc}"
        joined = f"{err_text}\n{suffix}" if err_text else suffix
        return CliRunResult(returncode=1, stdout=out, stderr=joined)
    return CliRunResult(returncode=int(result.exit_code or 0), stdout=out, stderr=err_text)


def _notify_progress_chunk(on_line: Optional[Callable[[str], None]], chunk: str) -> None:
    """按行或片段中的 ``[n/m]`` 触发进度回调（兼容 ``print(..., end='')``）。"""
    if not on_line or not chunk:
        return
    for line in chunk.splitlines():
        stripped = line.strip()
        if stripped:
            on_line(stripped)
    for match in _STEP_TAG_SCAN_RE.finditer(chunk):
        on_line(match.group(0).strip())


class _StreamTap:
    """包装 stdout/stderr，实时扫描步骤标记。"""

    def __init__(self, underlying, on_line: Optional[Callable[[str], None]]) -> None:
        self._underlying = underlying
        self._on_line = on_line
        self._pending = ""

    def write(self, data: str) -> int:
        if not data:
            return 0
        if self._underlying is None:
            _notify_progress_chunk(self._on_line, data)
            return len(data)
        written = self._underlying.write(data)
        self._pending += data
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            _notify_progress_chunk(self._on_line, line)
        if self._pending and _STEP_TAG_SCAN_RE.search(self._pending):
            _notify_progress_chunk(self._on_line, self._pending)
            self._pending = ""
        return written

    def flush(self) -> None:
        if self._underlying is not None:
            self._underlying.flush()
        if self._pending.strip():
            _notify_progress_chunk(self._on_line, self._pending.strip())
            self._pending = ""


@contextmanager
def _tap_stdio(on_line: Optional[Callable[[str], None]]) -> Iterator[None]:
    if on_line is None:
        yield
        return
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = _StreamTap(old_out, on_line)
    sys.stderr = _StreamTap(old_err, on_line)
    try:
        yield
    finally:
        if hasattr(sys.stdout, "flush"):
            sys.stdout.flush()
        if hasattr(sys.stderr, "flush"):
            sys.stderr.flush()
        sys.stdout = old_out
        sys.stderr = old_err


def _load_cli_main():
    """按 GUI profile 动态加载 CLI 入口（避免 core 包 import waterfall）。"""
    module = importlib.import_module(_cli_module())
    return module.main


def _invoke_click_inprocess(
    argv: Sequence[str],
    *,
    on_line: Optional[Callable[[str], None]] = None,
) -> CliRunResult:
    """进程内 Click（仅作无 agentctl.exe 时的回退；CliRunner 会缓冲 stdout）。"""
    main = _load_cli_main()
    args = _normalize_subcommand_argv(argv)

    runner = _make_cli_runner()
    with _tap_stdio(on_line):
        result = runner.invoke(main, args, prog_name=_cli_prog_name(), catch_exceptions=True)
    cli_result = _click_result_to_cli_run_result(result)
    if on_line and cli_result.stdout:
        for line in cli_result.stdout.splitlines():
            stripped = line.strip()
            if stripped:
                on_line(stripped)
    return cli_result


def invoke_agentctl_subprocess(
    cmd: Sequence[str],
    *,
    on_line: Optional[Callable[[str], None]] = None,
    process_holder: Optional[list] = None,
    timeout_seconds: Optional[float] = _DEFAULT_AGENTCTL_SUBPROCESS_TIMEOUT_S,
) -> CliRunResult:
    """隐藏子进程执行 agentctl，按行读取 stdout（供 GUI 实时进度）。"""
    from sdwan_desktop.core.app_paths import install_root
    from sdwan_desktop.core.subprocess_platform import popen_hidden

    cwd = install_root()
    popen_kw: dict = {}
    if cwd.is_dir():
        popen_kw["cwd"] = str(cwd)

    proc = popen_hidden(
        list(cmd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **popen_kw,
    )
    if process_holder is not None:
        process_holder.clear()
        process_holder.append(proc)

    chunks: list[str] = []
    read_err: list[BaseException] = []

    def _read_stdout() -> None:
        try:
            if proc.stdout is None:
                return
            for line in proc.stdout:
                chunks.append(line)
                _notify_progress_chunk(on_line, line.rstrip("\r\n"))
        except Exception as exc:
            read_err.append(exc)

    reader = threading.Thread(target=_read_stdout, daemon=True)
    reader.start()
    try:
        if timeout_seconds is not None:
            returncode = int(proc.wait(timeout=timeout_seconds))
        else:
            returncode = int(proc.wait())
    except subprocess.TimeoutExpired:
        proc.kill()
        returncode = int(proc.wait())
        logger.error("agentctl 子进程超时: %s", cmd[:4])
        return CliRunResult(
            returncode=124,
            stdout="".join(chunks),
            stderr="agentctl 子进程执行超时",
        )
    finally:
        reader.join(timeout=5.0)
        if process_holder is not None:
            process_holder.clear()
    if read_err:
        raise read_err[0]
    return CliRunResult(returncode=returncode, stdout="".join(chunks), stderr="")


def run_agentctl(
    argv: Sequence[str],
    *,
    on_line: Optional[Callable[[str], None]] = None,
    process_holder: Optional[list] = None,
) -> CliRunResult:
    """执行 agentctl 子命令。

    打包环境默认启动同目录 ``agentctl-core.exe`` / ``agentctl.exe``，以便捕获
  ``[n/m]`` 步骤输出；仅当找不到伴生可执行文件时才回退为进程内 Click。
    """
    cmd = resolve_agentctl_command(argv)
    use_subprocess = (
        sibling_agentctl_executable() is not None
        or not getattr(sys, "frozen", False)
    )
    if use_subprocess:
        logger.debug("agentctl subprocess: %s", cmd[:4])
        return invoke_agentctl_subprocess(
            cmd, on_line=on_line, process_holder=process_holder
        )
    logger.warning("未找到伴生 agentctl 可执行文件，回退进程内 Click（进度可能不刷新）")
    return _invoke_click_inprocess(argv, on_line=on_line)
