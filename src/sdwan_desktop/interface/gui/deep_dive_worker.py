"""深度诊断 GUI 后台线程：进程内 FlowRuntime（与一键体检相同，避免子进程卡死）。"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from sdwan_desktop.flow.handlers.deep_dive_steps import (
    handler_params_from_gui,
    run_deep_dive_flow,
)
from sdwan_desktop.interface.gui.flow_run_params import DeepDiveGuiRunParams

logger = logging.getLogger(__name__)


class DeepDiveWorker(QThread):
    """在 QThread 内直接执行 DEEP_DIVE_FLOW，并推送步骤进度。"""

    finished_ok = Signal(object)
    finished_err = Signal(str)
    progress_updated = Signal(int, str)

    def __init__(self, params: DeepDiveGuiRunParams, out_path: Path):
        super().__init__()
        self._gui_params = params
        self._out_path = out_path
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _progress(self, percent: int, text: str) -> None:
        self.progress_updated.emit(int(percent), text)

    async def _run_async(self) -> None:
        run_params = handler_params_from_gui(
            self._gui_params,
            self._out_path,
            progress=self._progress,
            cancelled=lambda: self._cancelled,
            console=False,
        )
        await run_deep_dive_flow(run_params)
        if not self._out_path.is_file():
            raise FileNotFoundError(f"未生成报告: {self._out_path}")

    def run(self) -> None:
        try:
            if self._cancelled:
                self.finished_err.emit("已取消")
                return
            self.progress_updated.emit(0, "正在启动深度诊断…")
            asyncio.run(self._run_async())
            if self._cancelled:
                self.finished_err.emit("已取消")
                return
            self.progress_updated.emit(100, "诊断完成")
            self.finished_ok.emit(self._out_path)
        except Exception as exc:
            logger.exception("深度诊断 GUI 执行失败")
            if not self._cancelled:
                self.finished_err.emit(_format_flow_error(exc))


def _format_flow_error(exc: BaseException) -> str:
    """展开 ``FlowError`` / ``__cause__``，便于对照步级超时或执行异常。"""
    from sdwan_desktop.core.errors.flow import FlowError

    parts: list[str] = []
    current: BaseException | None = exc
    seen = 0
    while current is not None and seen < 4:
        if isinstance(current, FlowError):
            parts.append(str(current))
        else:
            parts.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ if current.__cause__ is not current else None
        seen += 1
    return "\n".join(parts) if parts else str(exc)
