"""核心版 GUI 入口：不含业务监测与内嵌报告预览（供 onefile 瘦身包使用）。"""

from __future__ import annotations

import os
import sys

if getattr(sys, "frozen", False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

if application_path not in sys.path:
    sys.path.insert(0, application_path)

for path in (
    os.path.join(application_path, "src"),
    os.path.join(os.path.dirname(application_path), "src"),
    application_path,
):
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

from PySide6.QtWidgets import QApplication

from sdwan_desktop.interface.gui.app_branding import GUI_DISPLAY_NAME, GUI_CORE_DISPLAY_SUFFIX
from sdwan_desktop.interface.gui.app_icon import apply_app_icon, configure_platform_icon
from sdwan_desktop.core.subprocess_platform import ensure_gui_stdio
from sdwan_desktop.interface.gui.cli_runner import configure_gui_cli_profile, PROFILE_CORE
from sdwan_desktop.interface.gui.main_window import MainWindow, PROFILE_CORE

configure_gui_cli_profile(PROFILE_CORE)
ensure_gui_stdio()


def main() -> None:
    configure_platform_icon()
    app = QApplication([])
    core_title = f"{GUI_DISPLAY_NAME}{GUI_CORE_DISPLAY_SUFFIX}"
    app.setApplicationName(core_title)
    app.setApplicationDisplayName(core_title)
    window = MainWindow(profile=PROFILE_CORE)
    apply_app_icon(app, window)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
