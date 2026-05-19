"""合并 Worker 进度信号，降低主线程刷新频率。"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QTimer


class ProgressCoalescer:
    """在 GUI 主线程上合并 ``(percent, text)`` 更新（默认 200ms）。"""

    def __init__(
        self,
        on_update: Callable[[int, str], None],
        *,
        interval_ms: int = 200,
    ) -> None:
        self._on_update = on_update
        self._pending_percent = 0
        self._pending_text = ""
        self._dirty = False
        self._timer = QTimer()
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._flush)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._flush()

    def push(self, percent: int, text: str) -> None:
        self._pending_percent = max(self._pending_percent, int(percent))
        if text:
            self._pending_text = text
        self._dirty = True

    def _flush(self) -> None:
        if not self._dirty:
            return
        self._on_update(self._pending_percent, self._pending_text)
        self._dirty = False
        self._pending_text = ""


def connect_worker_progress(
    worker: object,
    slot: Callable[[int, str], None],
    *,
    interval_ms: int = 200,
) -> Optional[ProgressCoalescer]:
    """将 worker 的 ``progress_updated`` 经合并器接到 ``slot``；无信号时返回 ``None``。"""
    progress_sig = getattr(worker, "progress_updated", None)
    if progress_sig is None:
        return None
    coalescer = ProgressCoalescer(slot, interval_ms=interval_ms)
    coalescer.start()
    progress_sig.connect(coalescer.push)
    return coalescer
