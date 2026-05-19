"""GUI 无控制台环境下 stdout/stderr 为 None 时的防护。"""

from __future__ import annotations

import logging
import sys

from sdwan_desktop.core.subprocess_platform import ensure_gui_stdio
from sdwan_desktop.flow.handlers.deep_dive_steps import _configure_flow_logging


def test_ensure_gui_stdio_replaces_none_streams(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    import sdwan_desktop.core.subprocess_platform as sp

    monkeypatch.setattr(sp, "_gui_stdio_patched", False)
    ensure_gui_stdio()
    assert sys.stdout is not None
    assert sys.stderr is not None
    sys.stdout.write("x")
    sys.stdout.flush()


def test_configure_flow_logging_with_none_stderr(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stderr", None)
    import sdwan_desktop.core.subprocess_platform as sp

    monkeypatch.setattr(sp, "_gui_stdio_patched", False)
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    _configure_flow_logging(verbose=False)
    logging.getLogger("test.gui_stdio").info("ok")
