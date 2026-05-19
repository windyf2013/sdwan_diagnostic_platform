"""PyInstaller 构建共享配置（完整版 onedir / 核心版 onefile）。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

FLOW_HIDDEN_IMPORTS_BASE = [
    "sdwan_desktop.flow.definitions.quick_check",
    "sdwan_desktop.flow.definitions.deep_dive",
    "sdwan_desktop.flow.definitions.business_diagnose",
    "sdwan_desktop.flow.handlers.quick_check_steps",
    "sdwan_desktop.flow.handlers.deep_dive_steps",
]

FLOW_HIDDEN_IMPORTS = [
    *FLOW_HIDDEN_IMPORTS_BASE,
    "sdwan_desktop.interface.cli.main",
    "sdwan_desktop.interface.cli.commands.quick_check",
    "sdwan_desktop.interface.cli.commands.deep_dive",
    "sdwan_desktop.interface.cli.commands.business_diagnose",
    "sdwan_desktop.services.parser.vendor.cisco_sdwan",
    "sdwan_desktop.services.parser.vendor.raisecom_msg5200",
    "sdwan_desktop.services.parser.vendor.raisecom_msg5200b",
    "sdwan_desktop.services.reporter.html_builder",
    "sdwan_desktop.services.diagnosis.business_diagnose_followup",
    "sdwan_desktop.core.app_paths",
    "sdwan_desktop.core.subprocess_platform",
    "sdwan_desktop.tools.bootstrap",
]

FLOW_HIDDEN_IMPORTS_CORE = [
    *FLOW_HIDDEN_IMPORTS_BASE,
    "sdwan_desktop.interface.cli.main_core",
    "sdwan_desktop.interface.cli.bootstrap",
    "sdwan_desktop.interface.cli.commands.quick_check",
    "sdwan_desktop.interface.cli.commands.deep_dive",
    "sdwan_desktop.interface.cli.commands.business_diagnose",
    "sdwan_desktop.services.reporter.html_builder",
    "sdwan_desktop.services.reporter.deep_dive_report_presentation",
    "sdwan_desktop.services.reporter.joint_commercial_delivery",
    "sdwan_desktop.services.diagnosis.business_diagnose_followup",
    "sdwan_desktop.services.diagnosis.overlay_policy_flow_evidence",
    "sdwan_desktop.core.app_paths",
    "sdwan_desktop.core.subprocess_platform",
    "sdwan_desktop.tools.bootstrap",
]

PLAYWRIGHT_HIDDEN_IMPORTS = [
    "playwright",
    "playwright.async_api",
    "playwright.sync_api",
    "playwright._impl._driver",
    "sdwan_desktop.tools.adapters.playwright_adapter",
    "sdwan_desktop.tools.implementations.web.har_capture",
]

RUNTIME_HIDDEN_IMPORTS = [
    "PySide6",
    "dns",
    "tzdata",
    "paramiko",
    "telnetlib3",
    "jinja2",
    "wmi",
    "yaml",
    "click",
    "pydantic",
    "sdwan_desktop",
]

COMMON_EXCLUDES = [
    "asyncssh",
    "matplotlib",
    "numpy",
    "pandas",
    "scipy",
    "PIL",
    "tkinter",
    "_tkinter",
    "IPython",
    "pytest",
    "unittest",
    "test",
    "mypy",
    "mypyc",
    "mypy_extensions",
    "setuptools",
    "distutils",
]

QT_WEBENGINE_MODULES = [
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebChannel",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtOpenGL",
    "PySide6.QtPositioning",
    "PySide6.QtQuickWidgets",
]

CORE_EXTRA_EXCLUDES = [
    "playwright",
    "playwright.async_api",
    "playwright.sync_api",
    "sdwan_desktop.tools.adapters.playwright_adapter",
    "sdwan_desktop.tools.implementations.web.har_capture",
    "sdwan_desktop.interface.cli.commands.waterfall",
    *QT_WEBENGINE_MODULES,
]


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def data_args(root: Path) -> list[str]:
    sep = ";" if os.name == "nt" else ":"
    return [
        f"--paths={root / 'src'}",
        f"--add-data={root / 'configs'}{sep}configs",
        # 目标须为目录 assets/，否则 PyInstaller 会生成 assets/icon.ico/icon.ico
        f"--add-data={root / 'assets' / 'icon.ico'}{sep}assets",
        (
            f"--add-data={root / 'src' / 'sdwan_desktop' / 'reporting' / 'templates'}"
            f"{sep}sdwan_desktop/reporting/templates"
        ),
    ]


def hidden_import_args(names: list[str]) -> list[str]:
    return [f"--hidden-import={n}" for n in names]


def exclude_args(names: list[str]) -> list[str]:
    return [f"--exclude-module={n}" for n in names]


def clean_pycache(root: Path) -> None:
    for dirpath, dirnames, _filenames in os.walk(root):
        if "__pycache__" in dirnames:
            cache = Path(dirpath) / "__pycache__"
            try:
                shutil.rmtree(cache)
            except OSError:
                pass


def remove_dist(dist: Path, name: str, *, onedir: bool) -> None:
    if onedir:
        folder = dist / name
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
        return
    exe = dist / (f"{name}.exe" if os.name == "nt" else name)
    if exe.is_file():
        try:
            exe.unlink()
        except PermissionError:
            time.sleep(1)
            exe.unlink(missing_ok=True)


def bundle_playwright_chromium(dist: Path) -> Path:
    """Chromium 外挂目录：与 GUI onedir 同级 ``dist/ms-playwright``。"""
    browser_dir = dist / "ms-playwright"
    browser_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_dir)
    print(f"Installing Playwright Chromium -> {browser_dir}")
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        env=env,
        check=True,
        cwd=str(project_root()),
    )
    if not any(browser_dir.iterdir()):
        raise RuntimeError(f"Playwright browsers empty: {browser_dir}")
    return browser_dir
