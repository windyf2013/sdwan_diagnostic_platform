"""Windows 下隐藏控制台子进程（避免 GUI 运行时闪 CMD 窗口）。"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_gui_stdio_patched = False


def ensure_gui_stdio() -> None:
    """PyInstaller ``--windowed`` 下 ``sys.stdout`` / ``sys.stderr`` 常为 ``None``。

    深度诊断等流程会 ``logging.basicConfig`` 或 ``print(..., flush=True)``，
    若不对齐到可写流，会触发 ``'NoneType' object has no attribute 'flush'``。
    """
    global _gui_stdio_patched
    if _gui_stdio_patched:
        return
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")
    _gui_stdio_patched = True


def _create_no_window_flag() -> int:
    if sys.platform != "win32":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))


def hidden_startupinfo() -> Optional[subprocess.STARTUPINFO]:
    """构造隐藏窗口的 STARTUPINFO（仅 Windows）。"""
    if sys.platform != "win32":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


def subprocess_run_kwargs() -> Dict[str, Any]:
    """供 ``subprocess.run`` / ``Popen`` 使用的隐藏控制台参数。"""
    if sys.platform != "win32":
        return {}
    kw: Dict[str, Any] = {
        "creationflags": _create_no_window_flag(),
        "startupinfo": hidden_startupinfo(),
    }
    return kw


def asyncio_subprocess_kwargs() -> Dict[str, Any]:
    """供 ``asyncio.create_subprocess_exec`` 使用的隐藏控制台参数。"""
    if sys.platform != "win32":
        return {}
    return {"creationflags": _create_no_window_flag()}


def run_hidden(
    args: Sequence[str],
    *,
    capture_output: bool = False,
    text: bool = False,
    encoding: Optional[str] = None,
    errors: Optional[str] = None,
    check: bool = False,
    timeout: Optional[float] = None,
    **extra: Any,
) -> subprocess.CompletedProcess[str]:
    """``subprocess.run`` 包装：Windows 下不弹出 CMD。"""
    return subprocess.run(
        list(args),
        capture_output=capture_output,
        text=text,
        encoding=encoding,
        errors=errors,
        check=check,
        timeout=timeout,
        **subprocess_run_kwargs(),
        **extra,
    )


def popen_hidden(
    args: Sequence[str],
    *,
    stdout: Any = None,
    stderr: Any = None,
    stdin: Any = None,
    text: bool = False,
    encoding: Optional[str] = None,
    errors: Optional[str] = None,
    **extra: Any,
) -> subprocess.Popen[str]:
    """``subprocess.Popen`` 包装：Windows 下不弹出 CMD。"""
    return subprocess.Popen(
        list(args),
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        text=text,
        encoding=encoding,
        errors=errors,
        **subprocess_run_kwargs(),
        **extra,
    )


async def create_subprocess_exec_hidden(
    program: str,
    *cmd_args: str,
    stdout: Any = asyncio.subprocess.PIPE,
    stderr: Any = asyncio.subprocess.PIPE,
    **extra: Any,
) -> asyncio.subprocess.Process:
    """``asyncio.create_subprocess_exec`` 包装：Windows 下不弹出 CMD。"""
    return await asyncio.create_subprocess_exec(
        program,
        *cmd_args,
        stdout=stdout,
        stderr=stderr,
        **asyncio_subprocess_kwargs(),
        **extra,
    )


def reveal_path_in_file_manager(path: Path) -> None:
    """在资源管理器中定位文件（不弹出 CMD）。"""
    resolved = path.resolve()
    if sys.platform == "win32":
        run_hidden(
            ["explorer", "/select,", str(resolved)],
            check=False,
        )
        return
    import os

    folder = resolved if resolved.is_dir() else resolved.parent
    if sys.platform == "darwin":
        run_hidden(["open", str(folder)], check=False)
    else:
        run_hidden(["xdg-open", str(folder)], check=False)
