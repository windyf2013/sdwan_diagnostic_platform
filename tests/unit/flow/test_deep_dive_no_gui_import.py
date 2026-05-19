"""Flow handlers 不得经 GUI 包导入 PySide6（agentctl-core 无 Qt 依赖）。"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType


class _PySide6Blocker:
    """模拟无 PySide6 环境（与 PyInstaller agentctl-core 一致）。"""

    def find_spec(self, fullname: str, path=None, target=None):  # noqa: ANN001
        if fullname == "PySide6" or fullname.startswith("PySide6."):
            raise ModuleNotFoundError(f"No module named {fullname!r}")
        return None


def test_deep_dive_steps_import_without_pyside6() -> None:
    blocker = _PySide6Blocker()
    sys.meta_path.insert(0, blocker)
    # 清理可能已缓存的 gui 包（避免其它测试先加载 MainWindow）
    for key in list(sys.modules):
        if key == "PySide6" or key.startswith("PySide6."):
            sys.modules.pop(key, None)
        if key.startswith("sdwan_desktop.interface.gui"):
            sys.modules.pop(key, None)
    try:
        mod = importlib.import_module("sdwan_desktop.flow.handlers.deep_dive_steps")
        assert mod.DEEP_DIVE_STEP_COUNT == 9
        assert "PySide6" not in sys.modules
    finally:
        sys.meta_path.remove(blocker)


def test_gui_submodule_flow_run_params_without_loading_main_window() -> None:
    """``import gui.flow_run_params`` 不得拉起 ``gui.main_window``。"""
    blocker = _PySide6Blocker()
    sys.meta_path.insert(0, blocker)
    for key in list(sys.modules):
        if key.startswith("sdwan_desktop.interface.gui"):
            sys.modules.pop(key, None)
    try:
        mod = importlib.import_module("sdwan_desktop.interface.gui.flow_run_params")
        assert mod.DEEP_DIVE_DEFAULT_BIZ_TARGETS
        assert "sdwan_desktop.interface.gui.main_window" not in sys.modules
    finally:
        sys.meta_path.remove(blocker)
