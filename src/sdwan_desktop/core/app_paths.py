"""应用路径解析：开发环境与 PyInstaller 打包环境统一入口。"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# src/sdwan_desktop/core/app_paths.py -> parents[3] = 项目根
_DEV_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def is_frozen() -> bool:
    """是否为 PyInstaller 等打包后的可执行环境。"""
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """打包资源根目录（_MEIPASS）；开发环境等同项目根。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", _DEV_PROJECT_ROOT))
    return _DEV_PROJECT_ROOT


def install_root() -> Path:
    """可执行文件所在目录（用户可放置 configs/、reports/）；开发环境为项目根。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _DEV_PROJECT_ROOT


def project_root() -> Path:
    """逻辑项目根：开发时为仓库根；打包时优先安装目录（便于覆盖配置）。"""
    return install_root() if is_frozen() else _DEV_PROJECT_ROOT


def _resolve_icon_file(path: Path) -> Optional[Path]:
    """解析图标路径；兼容旧版打包误将 icon.ico 打成目录的情况。"""
    if path.is_file():
        return path
    nested = path / "icon.ico"
    if nested.is_file():
        return nested
    return None


def app_icon_path() -> Optional[Path]:
    """应用窗口/任务栏图标（assets/icon.ico）。"""
    rel = Path("assets", "icon.ico")
    for path in (
        bundle_root() / rel,
        install_root() / rel,
        _DEV_PROJECT_ROOT / rel,
    ):
        resolved = _resolve_icon_file(path)
        if resolved is not None:
            return resolved
    return None


def resolve_resource_path(*relative_parts: str) -> Optional[Path]:
    """按优先级解析资源文件：安装目录 > 打包内嵌 > 当前工作目录。

    Args:
        *relative_parts: 相对路径片段，如 ``configs``, ``quick_check.yaml``。

    Returns:
        首个存在的路径；均不存在时返回安装目录下的候选路径（便于创建）。
    """
    rel = Path(*relative_parts)
    candidates: Iterable[Path] = (
        install_root() / rel,
        bundle_root() / rel,
        Path.cwd() / rel,
        _DEV_PROJECT_ROOT / rel,
    )
    for path in candidates:
        if path.is_file() or path.is_dir():
            return path
    return install_root() / rel if is_frozen() else _DEV_PROJECT_ROOT / rel


def playwright_browsers_path() -> Optional[Path]:
    """定位打包随带的 Chromium 目录（``dist/ms-playwright``）。"""
    candidates = (
        install_root() / "ms-playwright",
        install_root().parent / "ms-playwright",
        bundle_root() / "ms-playwright",
        _DEV_PROJECT_ROOT / "dist" / "ms-playwright",
    )
    for path in candidates:
        if path.is_dir() and any(path.iterdir()):
            return path
    return None


def configure_playwright_browsers_path() -> None:
    """若未设置环境变量，则指向安装目录旁的 ``ms-playwright``（构建脚本写入）。"""
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return
    found = playwright_browsers_path()
    if found is not None:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(found)
        logger.debug("PLAYWRIGHT_BROWSERS_PATH=%s", found)
