"""
配置解析器服务模块

提供CPE设备配置解析的统一入口。
"""

from sdwan_desktop.core.types.cpe_config import (
    CpeConfiguration,
    InterfaceInfo,
    RouteEntry,
    SdwanPolicy,
    VpnTunnelInfo,
    NatRuleInfo,
)
from sdwan_desktop.services.parser.vendor import (
    VendorConfigParser,
    ConfigParserRegistry,
)

__all__ = [
    # 数据类
    "CpeConfiguration",
    "InterfaceInfo",
    "RouteEntry",
    "SdwanPolicy",
    "VpnTunnelInfo",
    "NatRuleInfo",
    # 解析器基类和注册中心
    "VendorConfigParser",
    "ConfigParserRegistry",
]
