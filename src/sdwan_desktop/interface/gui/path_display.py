"""GUI 路径展示助手：把内置/绝对的默认 YAML 路径转为相对当前工作目录的形式。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def display_default_yaml_path(absolute: Path, fallback_rel: str) -> Optional[str]:
    """把默认 YAML 文件的绝对路径转换为可展示的相对路径。

    GUI 启动时 CWD 可能与安装目录不同，将绝对路径硬编码进输入框会让 GUI
    在不同机器/不同启动位置间不可移植；优先按当前工作目录裁剪，否则回退
    到一个简短的相对默认（如 ``configs/cpe_credentials.yaml``）。

    Args:
        absolute: 由 ``default_*_path()`` 返回的候选路径（可能不存在）。
        fallback_rel: 当无法用 ``Path.relative_to`` 推出相对形式时使用的字符串。

    Returns:
        相对路径字符串；若文件不存在则返回 ``None``，由调用方决定是否留空。
    """
    if not absolute.is_file():
        return None
    try:
        return str(absolute.relative_to(Path.cwd()))
    except ValueError:
        return fallback_rel
