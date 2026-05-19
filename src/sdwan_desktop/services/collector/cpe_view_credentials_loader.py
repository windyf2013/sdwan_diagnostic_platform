"""
固定视图通用口令 YAML 加载（不按设备 IP 区分）。

默认文件：项目根 ``configs/cpe_view_credentials.yaml``（见 ``configs/cpe_view_credentials.example.yaml``）。
与 ``cpe_credentials.yaml`` 按设备管理登录/testnode 口令互补：本文件预置 testnode、diagnose、su、enable 等视图口令。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

import yaml

from sdwan_desktop.core.app_paths import resolve_resource_path

logger = logging.getLogger(__name__)

_VIEW_KEYS = ("testnode", "diagnose", "su", "enable")


def default_cpe_view_credentials_path() -> Path:
    """返回默认通用视图口令文件路径。"""
    resolved = resolve_resource_path("configs", "cpe_view_credentials.yaml")
    return Path(resolved) if resolved is not None else Path("configs") / "cpe_view_credentials.yaml"


def load_view_credentials_file(path: Path) -> Dict[str, Optional[str]]:
    """读取 YAML 中的 ``views`` 段，返回各视图口令（未配置为 None）。

    Args:
        path: YAML 文件路径。

    Returns:
        键为 ``testnode`` / ``diagnose`` / ``su`` / ``enable``，值为明文或 None。
    """
    empty = {k: None for k in _VIEW_KEYS}
    if not path.is_file():
        return dict(empty)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("读取通用视图口令文件失败 %s: %s", path, exc)
        return dict(empty)

    views = raw.get("views")
    if not isinstance(views, dict):
        return dict(empty)

    out: Dict[str, Optional[str]] = dict(empty)
    for key in _VIEW_KEYS:
        val = views.get(key)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            out[key] = None
        else:
            out[key] = str(val).strip()
    return out
