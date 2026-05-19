"""通用视图口令 YAML 加载单元测试。"""

from pathlib import Path

import pytest
import yaml

from sdwan_desktop.services.collector.cpe_view_credentials_loader import (
    load_view_credentials_file,
)


def test_load_missing_file_returns_empty_keys(tmp_path: Path) -> None:
    p = tmp_path / "none.yaml"
    got = load_view_credentials_file(p)
    assert got["testnode"] is None
    assert got["diagnose"] is None
    assert got["su"] is None
    assert got["enable"] is None


def test_load_views_section(tmp_path: Path) -> None:
    p = tmp_path / "v.yaml"
    p.write_text(
        yaml.safe_dump(
            {"views": {"testnode": "a", "diagnose": "b", "su": "", "enable": None}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    got = load_view_credentials_file(p)
    assert got["testnode"] == "a"
    assert got["diagnose"] == "b"
    assert got["su"] is None
    assert got["enable"] is None
