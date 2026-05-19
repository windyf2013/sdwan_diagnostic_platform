# scripts/build_core.py
"""核心功能包：onefile GUI（无业务监测/内嵌报告预览）+ 精简 agentctl。"""
from __future__ import annotations

import os

import PyInstaller.__main__

from pyi_common import (
    COMMON_EXCLUDES,
    CORE_EXTRA_EXCLUDES,
    FLOW_HIDDEN_IMPORTS_CORE,
    RUNTIME_HIDDEN_IMPORTS,
    clean_pycache,
    data_args,
    exclude_args,
    hidden_import_args,
    project_root,
    remove_dist,
)

GUI_NAME = "sdwan-diagnostic-core"
CLI_NAME = "agentctl-core"

# 核心 GUI：Qt Widgets，无 WebEngine / Playwright
GUI_HIDDEN = list(dict.fromkeys(RUNTIME_HIDDEN_IMPORTS + FLOW_HIDDEN_IMPORTS_CORE))
CLI_HIDDEN = list(
    dict.fromkeys(
        [h for h in GUI_HIDDEN if not h.startswith("PySide6")]
        + ["geoip2", "maxminddb"]
    )
)


def build_gui(root, dist) -> None:
    entry = root / "src/sdwan_desktop/interface/gui/main_window_core.py"
    PyInstaller.__main__.run(
        [
            str(entry),
            f"--name={GUI_NAME}",
            "--onefile",
            "--windowed",
            "--noupx",
            f"--icon={root / 'assets/icon.ico'}",
            *data_args(root),
            *hidden_import_args(GUI_HIDDEN),
            *exclude_args(COMMON_EXCLUDES + CORE_EXTRA_EXCLUDES),
            "--clean",
            f"--distpath={dist}",
            f"--workpath={root / 'build' / 'core' / 'gui'}",
            f"--specpath={root}",
        ]
    )


def build_agentctl(root, dist) -> None:
    entry = root / "src/sdwan_desktop/interface/cli/main_core.py"
    PyInstaller.__main__.run(
        [
            str(entry),
            f"--name={CLI_NAME}",
            "--onefile",
            "--console",
            "--noupx",
            *data_args(root),
            *hidden_import_args(CLI_HIDDEN),
            *exclude_args(COMMON_EXCLUDES + CORE_EXTRA_EXCLUDES + ["PySide6"]),
            "--clean",
            f"--distpath={dist}",
            f"--workpath={root / 'build' / 'core' / 'cli'}",
            f"--specpath={root}",
        ]
    )


def main() -> None:
    root = project_root()
    os.chdir(root)
    clean_pycache(root)
    dist = root / "dist"
    dist.mkdir(exist_ok=True)

    print("=== 核心版构建（onefile，无业务监测/内嵌预览）===")
    remove_dist(dist, GUI_NAME, onedir=False)
    build_gui(root, dist)
    remove_dist(dist, CLI_NAME, onedir=False)
    build_agentctl(root, dist)

    print("完成:")
    print(f"  GUI : dist/{GUI_NAME}.exe")
    print(f"  CLI : dist/{CLI_NAME}.exe")
    print("  说明: HTML 报告通过系统浏览器打开；不含 Playwright/Chromium。")


if __name__ == "__main__":
    main()
