import pytest
from PySide6.QtWidgets import QLineEdit
from sdwan_desktop.interface.gui.tabs.deep_dive_tab import DeepDiveTab, DeepDiveWorker


def test_deep_dive_tab_creation(qapp):
    """测试深度诊断标签页是否可以正常实例化"""
    tab = DeepDiveTab()
    assert tab is not None
    assert tab.host_input is not None
    assert tab.password_input.echoMode() == QLineEdit.Password


def test_deep_dive_worker_signals(qapp):
    """测试 DeepDiveWorker 信号定义"""
    worker = DeepDiveWorker({"host": "192.168.1.1"})
    assert hasattr(worker, 'progress_updated')
    assert hasattr(worker, 'diagnosis_completed')
    assert hasattr(worker, 'diagnosis_failed')


def test_save_report_button_initial_state(qapp):
    """测试保存报告按钮初始为禁用状态"""
    tab = DeepDiveTab()
    assert not tab.save_btn.isEnabled()
