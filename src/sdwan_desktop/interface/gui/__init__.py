"""GUI 包：延迟加载 ``MainWindow``，避免 ``import sdwan_desktop.interface.gui.*`` 时强制依赖 PySide6。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["MainWindow", "main"]


def __getattr__(name: str) -> Any:
    if name == "MainWindow":
        from sdwan_desktop.interface.gui.main_window import MainWindow

        return MainWindow
    if name == "main":
        from sdwan_desktop.interface.gui.main_window import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from sdwan_desktop.interface.gui.main_window import MainWindow, main
