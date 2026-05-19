"""深度诊断 Tab：启动 AgentctlWorker 与 CPE 口令前置校验。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtTest import QSignalSpy

from sdwan_desktop.interface.gui.deep_dive_worker import DeepDiveWorker
from sdwan_desktop.interface.gui.tabs.deep_dive_tab import DeepDiveTab


def test_deep_dive_tab_requires_cpe_auth(qapp) -> None:
    tab = DeepDiveTab()
    tab.host_input.setText("10.0.0.1")
    tab.username_input.setText("admin")
    tab.protocol.setCurrentText("ssh")
    assert tab._cpe_auth_error("10.0.0.1") is not None


def test_deep_dive_tab_starts_worker(qapp, tmp_path, monkeypatch) -> None:
    tab = DeepDiveTab()
    tab.host_input.setText("10.0.0.1")
    tab.username_input.setText("admin")
    tab.password_input.setText("secret")

    started: list[DeepDiveWorker] = []

    class FakeWorker(DeepDiveWorker):
        def start(self) -> None:
            started.append(self)
            self.progress_updated.emit(12, "[1/9] 采集 PC")
            out = Path(self._out_path)
            out.write_text("<html></html>", encoding="utf-8")
            self.finished_ok.emit(out)

    monkeypatch.setattr(
        "sdwan_desktop.interface.gui.tabs.deep_dive_tab.deep_dive_use_inprocess",
        lambda: True,
    )
    monkeypatch.setattr(
        "sdwan_desktop.interface.gui.tabs.deep_dive_tab.DeepDiveWorker",
        FakeWorker,
    )
    monkeypatch.setattr(
        "sdwan_desktop.interface.gui.tabs.deep_dive_tab.deliver_gui_report",
        lambda *_a, **_k: tmp_path / "report.html",
    )

    spy = QSignalSpy(tab.diagnosis_started)
    tab.on_start_diagnosis()

    assert len(started) == 1
    assert spy.count() == 1
    assert not tab.start_btn.isEnabled()
