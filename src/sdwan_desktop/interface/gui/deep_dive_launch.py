"""深度诊断 GUI 启动策略：默认子进程 agentctl，与 CLI 同宿主。"""

from __future__ import annotations

import os


def deep_dive_use_inprocess() -> bool:
    """为真时 GUI 在 QThread 内直接 ``run_deep_dive_flow``（调试回退）。"""
    return os.environ.get("SDWAN_DEEP_DIVE_INPROCESS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
