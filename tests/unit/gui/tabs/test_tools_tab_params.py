"""tools_tab 参数映射与目标数量约束。"""

from sdwan_desktop.interface.gui.tabs.tools_tab import ToolsTab


def test_build_tool_params_dns_uses_domain(qapp) -> None:
    tab = ToolsTab()
    tab.on_tool_changed("dns")
    params = tab._build_tool_params("dns", "www.example.com")
    assert params["domain"] == "www.example.com"
    assert "host" not in params


def test_build_tool_params_ping_uses_host(qapp) -> None:
    tab = ToolsTab()
    params = tab._build_tool_params("ping", "8.8.8.8")
    assert params["host"] == "8.8.8.8"
