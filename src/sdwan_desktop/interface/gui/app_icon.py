"""GUI 图标：开发环境与 PyInstaller 打包后统一设置窗口/任务栏图标。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow

from sdwan_desktop.core.app_paths import app_icon_path, is_frozen

if TYPE_CHECKING:
    pass

_APP_USER_MODEL_ID = "sdwan.desktop.diagnostic.gui.1"


def configure_platform_icon() -> None:
    """Windows 任务栏分组与图标关联（须在 QApplication 创建前调用）。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
    except Exception:
        pass


def load_app_icon() -> Optional[QIcon]:
    path = app_icon_path()
    if path is not None:
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    if is_frozen():
        exe_icon = QIcon(str(Path(sys.executable)))
        if not exe_icon.isNull():
            return exe_icon
    return None


def apply_app_icon(
    app: QApplication,
    window: Optional[QMainWindow] = None,
) -> None:
    icon = load_app_icon()
    if icon is None:
        return
    app.setWindowIcon(icon)
    if window is not None:
        window.setWindowIcon(icon)
