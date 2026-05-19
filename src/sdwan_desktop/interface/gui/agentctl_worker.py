"""GUI 后台执行 agentctl 子命令（可取消）。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence

from PySide6.QtCore import QThread, Signal

from sdwan_desktop.interface.gui.cli_runner import (
    CliRunResult,
    parse_cli_step_progress,
    resolve_agentctl_command,
    run_agentctl,
)

logger = logging.getLogger(__name__)


class AgentctlWorker(QThread):
    """在后台运行 agentctl 子命令；统一走隐藏子进程以获取实时步骤进度。"""

    finished_ok = Signal(object)  # Path
    finished_err = Signal(str)
    progress_updated = Signal(int, str)

    def __init__(self, argv: Sequence[str], out_path: Path):
        super().__init__()
        self._argv = list(argv)
        self._out_path = out_path
        self._process_holder: List[object] = []
        self._cancelled = False
        self._last_percent = 0

    def cancel(self) -> None:
        self._cancelled = True
        if self._process_holder:
            proc = self._process_holder[0]
            poll = getattr(proc, "poll", None)
            terminate = getattr(proc, "terminate", None)
            if callable(poll) and callable(terminate) and poll() is None:
                terminate()

    def _on_cli_line(self, line: str) -> None:
        parsed = parse_cli_step_progress(line)
        if parsed is not None:
            percent, text = parsed
            self._last_percent = percent
            self.progress_updated.emit(percent, text)
            return
        if line:
            self.progress_updated.emit(self._last_percent, line[:160])

    def _finish_from_result(self, result: CliRunResult) -> None:
        if self._cancelled:
            self.finished_err.emit("已取消")
            return
        if result.returncode != 0:
            parts: list[str] = []
            so = (result.stdout or "").strip()
            se = (result.stderr or "").strip()
            if so:
                parts.append(so)
            if se:
                parts.append(se)
            tail = "\n".join(parts)[-4000:]
            self.finished_err.emit(
                f"退出码 {result.returncode}\n{tail}" if tail else f"退出码 {result.returncode}"
            )
            return
        if not self._out_path.is_file():
            self.finished_err.emit(f"未找到输出文件: {self._out_path}")
            return
        self.progress_updated.emit(100, "诊断完成")
        self.finished_ok.emit(self._out_path)

    def run(self) -> None:
        try:
            if self._cancelled:
                self.finished_err.emit("已取消")
                return
            cmd = resolve_agentctl_command(self._argv)
            logger.info("agentctl worker start: %s", cmd[: min(5, len(cmd))])
            self.progress_updated.emit(0, "正在启动诊断…")
            result = run_agentctl(
                self._argv,
                on_line=self._on_cli_line,
                process_holder=self._process_holder,
            )
            self._finish_from_result(result)
        except Exception as exc:
            logger.exception("agentctl 后台任务失败: %s", self._argv[:3])
            if not self._cancelled:
                self.finished_err.emit(str(exc))
