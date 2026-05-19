"""
厂商配置解析器模块

提供多厂商CPE设备配置解析的抽象层和注册中心。
遵循 SDWAN_SPEC.md §2.4 工具系统规范
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration

logger = logging.getLogger(__name__)


class VendorConfigParser(ABC):
    """厂商配置解析器抽象基类
    
    所有厂商特定的配置解析器必须继承此类，
    实现统一的解析接口以支持多厂商设备。
    """
    
    @abstractmethod
    def get_vendor_name(self) -> str:
        """返回厂商名称标识
        
        Returns:
            厂商名称字符串，如 "cisco_sdwan", "huawei" 等
        """
        pass
    
    @abstractmethod
    def detect_vendor(self, raw_output: str) -> bool:
        """检测是否为该厂商设备
        
        通过分析命令输出来识别设备厂商。
        
        Args:
            raw_output: 设备命令输出（通常是 show version）
            
        Returns:
            True 如果检测到是该厂商设备
        """
        pass
    
    @abstractmethod
    def parse_all(self, command_outputs: Dict[str, str]) -> CpeConfiguration:
        """解析所有命令输出，构建完整的 CpeConfiguration
        
        Args:
            command_outputs: 命令名到输出的映射
            
        Returns:
            解析后的 CpeConfiguration 对象
        """
        pass


class ConfigParserRegistry:
    """配置解析器注册中心
    
    管理所有已注册的厂商解析器，提供自动检测和解析功能。
    """
    
    def __init__(self):
        self._parsers: Dict[str, VendorConfigParser] = {}
    
    def register(self, parser: VendorConfigParser):
        """注册一个厂商解析器
        
        Args:
            parser: VendorConfigParser 实例
        """
        name = parser.get_vendor_name()
        self._parsers[name] = parser
    
    def _detect_and_parse_impl(self, command_outputs: Dict[str, str]) -> Optional[CpeConfiguration]:
        """自动检测设备厂商并解析配置
        
        Args:
            command_outputs: 命令名到输出的映射
            
        Returns:
            解析后的 CpeConfiguration 对象，如果无法识别厂商则返回 None
        """
        # 尝试使用每个解析器的 detect_vendor 方法
        for name, parser in self._parsers.items():
            # 通常使用 show version 或类似命令的输出来检测
            version_output = command_outputs.get("show version", "")
            if not version_output:
                # 如果没有 show version，尝试其他可能的命令
                version_output = "\n".join(command_outputs.values())
            
            if parser.detect_vendor(version_output):
                logger.info(f"Detected vendor: {name}")
                return parser.parse_all(command_outputs)
        
        logger.warning("Could not detect vendor from command outputs")
        return None

    def detect_and_parse(self, command_outputs: Dict[str, str]) -> Optional[CpeConfiguration]:
        """自动检测设备厂商并解析配置（实例方法包装）"""
        return self._detect_and_parse_impl(command_outputs)

    def clear(self):
        """清空所有已注册的解析器（主要用于测试）"""
        self._parsers.clear()

    @classmethod
    def clear_all(cls):
        """清空全局注册表中的所有解析器（主要用于测试）"""
        _get_registry().clear()

    @classmethod
    def list_vendors(cls) -> List[str]:
        """列出所有已注册的厂商名称"""
        return list(_get_registry()._parsers.keys())

    @classmethod
    def get_parser(cls, vendor_name: str) -> Optional[VendorConfigParser]:
        """获取指定厂商的解析器"""
        return _get_registry()._parsers.get(vendor_name)

    @classmethod
    def detect_and_parse(cls, command_outputs: Dict[str, str]) -> Optional[CpeConfiguration]:
        """自动检测设备厂商并解析配置（类方法包装）"""
        return _get_registry()._detect_and_parse_impl(command_outputs)

    @classmethod
    def register(cls, parser: 'VendorConfigParser'):
        """向全局注册表注册一个解析器（主要用于测试）"""
        # 直接操作内部字典以避免触发实例方法导致的递归
        _get_registry()._parsers[parser.get_vendor_name()] = parser


# 延迟导入具体的解析器实现以避免循环导入
def _get_registry():
    """获取单例注册表并初始化解析器"""
    if not hasattr(_get_registry, "_registry"):
        from .cisco_sdwan import CiscoSdwanParser
        from .raisecom_msg5200 import RaisecomMsg5200Parser
        from .raisecom_msg5200b import RaisecomMsg5200BParser

        registry = ConfigParserRegistry()
        # 直接操作内部字典以避免触发类方法导致的递归
        registry._parsers[CiscoSdwanParser().get_vendor_name()] = CiscoSdwanParser()
        # 5200B 需在 5200A 之前注册，保证 ``list_vendors`` / 探测顺序优先匹配 XGE 产品线
        registry._parsers[RaisecomMsg5200BParser().get_vendor_name()] = RaisecomMsg5200BParser()
        registry._parsers[RaisecomMsg5200Parser().get_vendor_name()] = RaisecomMsg5200Parser()
        _get_registry._registry = registry
    return _get_registry._registry

# 导出全局注册表实例
registry = _get_registry()
