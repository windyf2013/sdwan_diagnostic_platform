import pytest
from sdwan_desktop.interface.gui.tabs.waterfall_tab import WaterfallTab, WaterfallWorker


def test_waterfall_tab_creation(qapp):
    """测试业务监测标签页是否可以正常实例化"""
    tab = WaterfallTab()
    assert tab is not None
    assert tab.url_input is not None
    assert tab.start_btn is not None


def test_waterfall_worker_signals(qapp):
    """测试 WaterfallWorker 信号定义"""
    worker = WaterfallWorker("https://example.com")
    assert hasattr(worker, 'progress_updated')
    assert hasattr(worker, 'monitoring_completed')
    assert hasattr(worker, 'monitoring_failed')


def test_url_validation_logic(qapp):
    """测试 URL 输入校验逻辑"""
    tab = WaterfallTab()
    
    # 模拟无效 URL
    tab.url_input.setText("www.example.com")
    tab.on_start_monitoring()
    assert "错误" in tab.status_label.text()
    
    # 模拟有效 URL (仅检查 UI 状态变化，不实际执行)
    tab.url_input.setText("https://example.com")
    tab.start_btn.setEnabled(True) # 重置按钮状态
