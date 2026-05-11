"""
配置管理模块 - 加载和管理一键体检配置

提供 QuickCheckConfig 数据类和 ConfigLoader 加载器，
将 configs/quick_check.yaml 转换为结构化数据。

遵循 SDWAN_SPEC.md §2.1 数据结构规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
"""

from .loader import ConfigLoader, QuickCheckConfig, ProbeTargetConfig, ThresholdConfig

__all__ = [
    "ConfigLoader",
    "QuickCheckConfig",
    "ProbeTargetConfig",
    "ThresholdConfig",
]
