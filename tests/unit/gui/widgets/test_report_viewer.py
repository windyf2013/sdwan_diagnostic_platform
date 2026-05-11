import pytest
from sdwan_desktop.interface.gui.widgets.report_viewer import ReportViewer


def test_report_viewer_creation(qapp):
    """测试报告预览组件是否可以正常实例化"""
    viewer = ReportViewer()
    assert viewer is not None
    assert viewer.browser is not None
    assert viewer.open_btn is not None
