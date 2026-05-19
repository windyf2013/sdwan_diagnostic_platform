"""app_icon_path：开发环境与 PyInstaller 误打包目录的兼容。"""

from pathlib import Path

from sdwan_desktop.core.app_paths import _resolve_icon_file, app_icon_path


def test_app_icon_path_dev_project():
    path = app_icon_path()
    assert path is not None
    assert path.is_file()
    assert path.name == "icon.ico"


def test_resolve_icon_file_nested_pyinstaller_layout(tmp_path: Path):
    wrong_dir = tmp_path / "assets" / "icon.ico"
    wrong_dir.mkdir(parents=True)
    real = wrong_dir / "icon.ico"
    real.write_bytes(b"\x00\x01")
    assert _resolve_icon_file(wrong_dir) == real
