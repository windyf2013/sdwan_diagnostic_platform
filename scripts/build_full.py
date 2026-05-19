# scripts/build_full.py
"""完整功能包：onedir GUI + agentctl + 外挂 Chromium（dist/ms-playwright）。"""
from __future__ import annotations

import os

import PyInstaller.__main__

from pyi_common import (
    COMMON_EXCLUDES,
    FLOW_HIDDEN_IMPORTS,
    PLAYWRIGHT_HIDDEN_IMPORTS,
    RUNTIME_HIDDEN_IMPORTS,
    bundle_playwright_chromium,
    clean_pycache,
    data_args,
    exclude_args,
    hidden_import_args,
    project_root,
    remove_dist,
)

_root = project_root()
import sys

if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))

from sdwan_desktop.interface.gui.app_branding import GUI_EXECUTABLE_NAME

GUI_NAME = GUI_EXECUTABLE_NAME
CLI_NAME = "agentctl"

GUI_HIDDEN = list(
    dict.fromkeys(RUNTIME_HIDDEN_IMPORTS + FLOW_HIDDEN_IMPORTS + PLAYWRIGHT_HIDDEN_IMPORTS)
)
CLI_HIDDEN = list(dict.fromkeys(GUI_HIDDEN + ["geoip2", "maxminddb"]))


def build_gui(root, dist) -> None:
    entry = root / "src/sdwan_desktop/interface/gui/main_window.py"
    PyInstaller.__main__.run(
        [
            str(entry),
            f"--name={GUI_NAME}",
            "--onedir",
            "--windowed",
            "--noupx",
            f"--icon={root / 'assets/icon.ico'}",
            "--collect-all=playwright",
            *data_args(root),
            *hidden_import_args(GUI_HIDDEN),
            *exclude_args(COMMON_EXCLUDES),
            "--clean",
            f"--distpath={dist}",
            f"--workpath={root / 'build' / 'full' / 'gui'}",
            f"--specpath={root}",
        ]
    )


def build_agentctl(root, dist) -> None:
    entry = root / "src/sdwan_desktop/interface/cli/main.py"
    PyInstaller.__main__.run(
        [
            str(entry),
            f"--name={CLI_NAME}",
            "--onefile",
            "--console",
            "--noupx",
            "--collect-all=playwright",
            *data_args(root),
            *hidden_import_args(CLI_HIDDEN),
            *exclude_args(
                COMMON_EXCLUDES
                + [
                    "PySide6",
                    "PySide6.QtCore",
                    "PySide6.QtGui",
                    "PySide6.QtWidgets",
                ]
            ),
            "--clean",
            f"--distpath={dist}",
            f"--workpath={root / 'build' / 'full' / 'cli'}",
            f"--specpath={root}",
        ]
    )


def main() -> None:
    root = project_root()
    os.chdir(root)
    clean_pycache(root)
    dist = root / "dist"
    dist.mkdir(exist_ok=True)

    print("=== 完整版构建（onedir + 外挂 Chromium）===")
    remove_dist(dist, GUI_NAME, onedir=True)
    build_gui(root, dist)
    remove_dist(dist, CLI_NAME, onedir=False)
    build_agentctl(root, dist)
    bundle_playwright_chromium(dist)

    print("完成:")
    print(f"  GUI : dist/{GUI_NAME}/{GUI_NAME}.exe")
    print(f"  CLI : dist/{CLI_NAME}.exe")
    print("  浏览器: dist/ms-playwright/ （须与 GUI 目录一并分发）")


if __name__ == "__main__":
    main()
