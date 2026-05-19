"""按需注册探测工具，避免 GUI 启动时加载全部实现模块。"""

from __future__ import annotations

_core_registered = False
_har_registered = False


def ensure_core_tools_registered() -> None:
    """注册一键体检 / 业务探测 / 网络工具页所需工具（不含 Playwright HAR）。"""
    global _core_registered
    if _core_registered:
        return
    import sdwan_desktop.tools.implementations.system.windows  # noqa: F401
    import sdwan_desktop.tools.implementations.network.ping  # noqa: F401
    import sdwan_desktop.tools.implementations.network.dns  # noqa: F401
    import sdwan_desktop.tools.implementations.network.tcping  # noqa: F401
    import sdwan_desktop.tools.implementations.network.traceroute  # noqa: F401

    _core_registered = True


def ensure_har_tool_registered() -> None:
    """注册业务监测 HAR 工具（依赖 Playwright，仅在使用该功能时调用）。"""
    global _har_registered
    ensure_core_tools_registered()
    if _har_registered:
        return
    import sdwan_desktop.tools.implementations.web.har_capture  # noqa: F401

    _har_registered = True
