"""
CPE 设备凭证 YAML 加载。

默认文件路径：项目根下 ``configs/cpe_credentials.yaml``（见 ``configs/cpe_credentials.example.yaml``）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from sdwan_desktop.core.app_paths import resolve_resource_path

logger = logging.getLogger(__name__)


def default_cpe_credentials_path() -> Path:
    """返回默认凭证文件路径（项目根 ``configs/cpe_credentials.yaml``）。"""
    resolved = resolve_resource_path("configs", "cpe_credentials.yaml")
    return Path(resolved) if resolved is not None else Path("configs") / "cpe_credentials.yaml"


def load_device_credentials_file(path: Path, host: str) -> Dict[str, Optional[str]]:
    """从 YAML 读取指定主机的可选凭证。

    Args:
        path: YAML 文件路径。
        host: CPE 主机地址（与 YAML 中 ``devices`` 键一致）。

    Returns:
        字典键 ``password``、``testnode_password``，未配置时为 None。
    """
    if not path.is_file():
        return {"password": None, "testnode_password": None}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("读取 CPE 凭证文件失败 %s: %s", path, exc)
        return {"password": None, "testnode_password": None}

    devices: Dict[str, Any] = raw.get("devices") or {}
    entry: Any = devices.get(host) or devices.get(str(host))
    if not isinstance(entry, dict):
        return {"password": None, "testnode_password": None}

    pwd = entry.get("password")
    tnp = entry.get("testnode_password")
    return {
        "password": str(pwd) if pwd is not None and str(pwd) != "" else None,
        "testnode_password": str(tnp) if tnp is not None and str(tnp) != "" else None,
    }
