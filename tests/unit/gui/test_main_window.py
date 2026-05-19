import pytest
from sdwan_desktop.interface.gui.app_branding import GUI_DISPLAY_NAME
from sdwan_desktop.interface.gui.main_window import MainWindow


def test_main_window_creation(qapp):
    """测试主窗口是否可以正常实例化"""
    window = MainWindow()
    assert window is not None
    assert window.windowTitle() == GUI_DISPLAY_NAME
    assert window.minimumWidth() == 1000
    assert window.minimumHeight() == 700


def test_tabs_exist(qapp):
    """测试功能标签页是否已创建"""
    window = MainWindow()
    tab_widget = window.tab_widget

    assert tab_widget.count() == 6
    assert tab_widget.tabText(0) == "网络工具"
    assert tab_widget.tabText(1) == "一键体检"
    assert tab_widget.tabText(2) == "业务路径诊断"
    assert tab_widget.tabText(3) == "深度诊断"
    assert tab_widget.tabText(4) == "业务监测"
    assert tab_widget.tabText(5) == "报告预览"


def test_status_bar_ready(qapp):
    """测试状态栏初始显示 '就绪'"""
    window = MainWindow()
    status_label = window.status_label
    assert status_label.text() == "就绪"


def test_progress_bar_initially_hidden(qapp):
    """测试进度条初始为隐藏状态"""
    window = MainWindow()
    progress_bar = window.progress_bar
    assert not progress_bar.isVisible()


def test_tools_tab_integration(qapp):
    """测试网络工具标签页是否正确集成"""
    window = MainWindow()
    tools_tab = window.tools_tab
    
    # 检查标签页类型
    from sdwan_desktop.interface.gui.tabs.tools_tab import ToolsTab
    assert isinstance(tools_tab, ToolsTab)
    
    # 检查基本组件是否存在
    assert tools_tab.tool_combo is not None
    assert tools_tab.target_input is not None
    assert tools_tab.execute_btn is not None
    assert tools_tab.output_text is not None


def test_quick_check_tab_integration(qapp):
    """测试一键体检标签页是否正确集成"""
    window = MainWindow()
    quick_check_tab = window.quick_check_tab
    
    # 检查标签页类型
    from sdwan_desktop.interface.gui.tabs.quick_check_tab import QuickCheckTab
    assert isinstance(quick_check_tab, QuickCheckTab)
    
    # 检查基本组件是否存在
    assert quick_check_tab.start_btn is not None
    assert quick_check_tab.preview_btn is not None
    assert quick_check_tab.result_table is not None


def test_deep_dive_tab_integration(qapp):
    """测试深度诊断标签页是否正确集成"""
    window = MainWindow()
    deep_dive_tab = window.deep_dive_tab
    
    # 检查标签页类型
    from sdwan_desktop.interface.gui.tabs.deep_dive_tab import DeepDiveTab
    assert isinstance(deep_dive_tab, DeepDiveTab)
    
    # 检查基本组件是否存在
    assert deep_dive_tab.host_input is not None
    assert deep_dive_tab.password_input is not None
    assert deep_dive_tab.start_btn is not None


def test_waterfall_tab_integration(qapp):
    """测试业务监测标签页是否正确集成"""
    window = MainWindow()
    waterfall_tab = window.waterfall_tab
    
    # 检查标签页类型
    from sdwan_desktop.interface.gui.tabs.waterfall_tab import WaterfallTab
    assert isinstance(waterfall_tab, WaterfallTab)
    
    # 检查基本组件是否存在
    assert waterfall_tab.url_input is not None
    assert waterfall_tab.start_btn is not None
    assert waterfall_tab.save_btn is not None


def test_report_viewer_integration(qapp):
    """测试报告预览标签页是否正确集成"""
    window = MainWindow()
    report_viewer = window.report_viewer
    
    # 检查标签页类型
    from sdwan_desktop.interface.gui.widgets.report_viewer import ReportViewer
    assert isinstance(report_viewer, ReportViewer)
    
    # 检查基本组件是否存在
    assert report_viewer.browser is not None
    assert report_viewer.open_btn is not None


def test_theme_toggle_functionality(qapp):
    """测试主题切换功能"""
    window = MainWindow()
    assert window.current_theme == "light"
    
    # 模拟切换
    window.toggle_theme()
    assert window.current_theme == "dark"
    
    window.toggle_theme()
    assert window.current_theme == "light"
