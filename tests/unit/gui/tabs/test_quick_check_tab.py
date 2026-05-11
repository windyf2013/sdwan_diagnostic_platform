import pytest
from sdwan_desktop.interface.gui.tabs.quick_check_tab import QuickCheckTab, QuickCheckWorker


def test_quick_check_tab_creation(qapp):
    """测试一键体检标签页是否可以正常实例化"""
    tab = QuickCheckTab()
    assert tab is not None
    assert tab.start_btn is not None
    assert tab.result_table is not None


def test_quick_check_worker_signals(qapp):
    """测试 QuickCheckWorker 信号定义"""
    worker = QuickCheckWorker()
    assert hasattr(worker, 'progress_updated')
    assert hasattr(worker, 'diagnosis_completed')
    assert hasattr(worker, 'diagnosis_failed')


def test_save_report_button_initial_state(qapp):
    """测试保存报告按钮初始为禁用状态"""
    tab = QuickCheckTab()
    assert not tab.save_btn.isEnabled()
