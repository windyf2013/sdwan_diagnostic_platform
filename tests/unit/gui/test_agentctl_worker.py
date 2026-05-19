"""AgentctlWorker：CLI 步骤进度解析与后台执行。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from sdwan_desktop.interface.gui.agentctl_worker import AgentctlWorker
from sdwan_desktop.interface.gui.cli_runner import CliRunResult, parse_cli_step_progress


def test_parse_cli_step_progress_deep_dive() -> None:
    parsed = parse_cli_step_progress("[2/8] 连接 CPE 设备...")
    assert parsed is not None
    percent, text = parsed
    assert percent == 25
    assert "[2/8]" in text


def test_agentctl_worker_emits_progress(qapp, tmp_path) -> None:
    out = tmp_path / "report.html"
    out.write_text("<html></html>", encoding="utf-8")

    worker = AgentctlWorker(["deep-dive", "-o", str(out)], out)
    progress: list[tuple[int, str]] = []
    worker.progress_updated.connect(
        lambda pct, text: progress.append((pct, text))
    )

    worker._on_cli_line("[3/8] CPE collect")
    assert any(pct > 0 for pct, _ in progress)
    assert any("[3/8]" in text for _, text in progress)
