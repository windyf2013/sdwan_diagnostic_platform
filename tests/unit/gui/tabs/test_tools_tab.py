from sdwan_desktop.interface.gui.tabs.tools_tab import ToolsTab


def test_tools_tab_loads_registered_tools(qapp) -> None:
    tab = ToolsTab()
    assert tab.tool_combo.count() >= 1
    assert tab.tool_combo.isEnabled()
    assert tab.tool_combo.currentText() in ("ping", "dns", "tcping", "traceroute")
