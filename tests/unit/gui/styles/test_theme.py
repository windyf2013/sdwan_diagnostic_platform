import pytest
from sdwan_desktop.interface.gui.styles.theme import ThemeManager


def test_theme_manager_exists(qapp):
    """测试主题管理器是否可以正常导入和访问"""
    assert hasattr(ThemeManager, 'LIGHT_THEME')
    assert hasattr(ThemeManager, 'DARK_THEME')
    assert hasattr(ThemeManager, 'apply_theme')


def test_apply_theme_no_crash(qapp):
    """测试应用主题时不会崩溃"""
    # 仅测试方法调用，不验证具体样式效果（因为 Qt 样式应用是异步且复杂的）
    ThemeManager.apply_theme("light")
    ThemeManager.apply_theme("dark")
