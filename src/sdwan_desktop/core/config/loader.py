"""
配置加载器 - 加载一键体检配置并转换为结构化数据

将 configs/quick_check.yaml 转换为 QuickCheckConfig 数据类，
供 ConnectivityTester、DnsSplitTester 等服务层使用。

遵循 SDWAN_SPEC.md §2.1 数据结构规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# ==================== 配置数据类 ====================


@dataclass(slots=True)
class ProbeTargetConfig:
    """探测目标配置

    定义单个探测目标的主机地址和探测协议类型。
    """

    host: str
    """目标主机地址（IP或域名）"""

    type: str = "icmp"
    """探测协议类型: icmp / http / https / tcp"""


@dataclass(slots=True)
class ThresholdConfig:
    """阈值配置

    定义各项检测的告警阈值。
    """

    gateway_rtt_warning_ms: int = 100
    """网关延迟告警阈值(ms)"""

    gateway_loss_warning_pct: int = 5
    """网关丢包告警阈值(%)"""

    dns_timeout_ms: int = 2000
    """DNS超时阈值(ms)"""

    dns_slow_ms: int = 500
    """DNS响应慢阈值(ms)"""

    international_loss_warning_pct: int = 10
    """国际链路丢包告警阈值(%)"""


@dataclass(slots=True)
class QuickCheckConfig:
    """一键体检配置

    聚合所有一键体检相关的配置项，包括采集开关、探测目标、阈值等。
    从 configs/quick_check.yaml 加载。
    """

    # ==================== 采集开关 ====================
    collection_adapters: bool = True
    """是否采集网卡适配器信息"""

    collection_routes: bool = True
    """是否采集路由表"""

    collection_dns: bool = True
    """是否采集DNS配置"""

    collection_proxy: bool = True
    """是否采集代理配置"""

    collection_firewall: bool = True
    """是否采集防火墙状态"""

    collection_arp: bool = True
    """是否采集ARP表"""

    collection_ipv6: bool = True
    """是否采集IPv6信息"""

    # ==================== DNS服务器 ====================
    domestic_dns_servers: List[str] = field(default_factory=lambda: [
        "114.114.114.114",
        "223.5.5.5",
    ])
    """国内DNS服务器列表"""

    international_dns_servers: List[str] = field(default_factory=lambda: [
        "8.8.8.8",
        "1.1.1.1",
    ])
    """国际DNS服务器列表"""

    # ==================== 连通性目标 ====================
    domestic_targets: List[ProbeTargetConfig] = field(default_factory=lambda: [
        ProbeTargetConfig(host="www.baidu.com", type="http"),
        ProbeTargetConfig(host="114.114.114.114", type="icmp"),
    ])
    """国内连通性测试目标列表"""

    international_targets: List[ProbeTargetConfig] = field(default_factory=lambda: [
        ProbeTargetConfig(host="www.google.com", type="http"),
        ProbeTargetConfig(host="www.youtube.com", type="http"),
        ProbeTargetConfig(host="www.tiktok.com", type="http"),
        ProbeTargetConfig(host="8.8.8.8", type="icmp"),
    ])
    """国际连通性测试目标列表"""

    # ==================== DNS分流测试域名 ====================
    dns_split_domains: List[str] = field(default_factory=lambda: [
        "www.baidu.com",
        "www.google.com",
        "www.youtube.com",
        "www.tiktok.com",
    ])
    """DNS分流测试域名列表"""

    # ==================== 阈值 ====================
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    """各项检测的告警阈值"""

    # ==================== 并发控制 ====================
    max_concurrent_probes: int = 5
    """最大并发探测数"""

    max_concurrent_dns_queries: int = 3
    """最大并发DNS查询数"""

    probe_interval: float = 0.5
    """探测间隔(秒)"""

    # ==================== 元信息 ====================
    config_version: str = "1.0.0"
    """配置版本号"""

    def to_target_dicts(self, targets: List[ProbeTargetConfig]) -> List[Dict[str, Any]]:
        """将 ProbeTargetConfig 列表转换为 dict 列表

        供 ConnectivityTester 的 test_domestic_targets / test_international_targets 使用。

        Args:
            targets: ProbeTargetConfig 列表

        Returns:
            List[Dict[str, Any]]: 包含 host 和 type 的 dict 列表
        """
        return [{"host": t.host, "type": t.type} for t in targets]


# ==================== 配置加载器 ====================


class ConfigLoader:
    """配置加载器

    从 YAML 文件加载一键体检配置，并转换为 QuickCheckConfig 数据类。
    遵循 PATCH-002: 在边界处将 dict 转换为结构化对象。
    """

    def __init__(self, config_path: Optional[str] = None):
        """初始化配置加载器

        Args:
            config_path: 配置文件路径，默认为项目根目录下的 configs/quick_check.yaml
        """
        if config_path is None:
            # 默认路径：项目根目录 / configs / quick_check.yaml
            self.config_path = self._find_default_config()
        else:
            self.config_path = config_path

        self._raw_config: Dict[str, Any] = {}

    def _find_default_config(self) -> str:
        """查找默认配置文件路径

        从项目根目录的 configs/quick_check.yaml 加载。

        Returns:
            str: 配置文件绝对路径
        """
        from sdwan_desktop.core.app_paths import resolve_resource_path

        resolved = resolve_resource_path("configs", "quick_check.yaml")
        if resolved is not None and resolved.is_file():
            return str(resolved)

        fallback = os.path.normpath(os.path.join(os.getcwd(), "configs", "quick_check.yaml"))
        return fallback

    def load(self) -> QuickCheckConfig:
        """加载并解析配置文件

        读取 YAML 文件，将原始 dict 转换为 QuickCheckConfig 数据类。

        Returns:
            QuickCheckConfig: 结构化的配置对象

        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML 解析错误
        """
        if not os.path.exists(self.config_path):
            logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
            return QuickCheckConfig()

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if raw is None:
            logger.warning(f"配置文件为空: {self.config_path}，使用默认配置")
            return QuickCheckConfig()

        self._raw_config = raw
        return self._parse_config(raw)

    def _parse_config(self, raw: Dict[str, Any]) -> QuickCheckConfig:
        """将原始 dict 解析为 QuickCheckConfig

        遵循 PATCH-002: 在边界处将 dict 转换为结构化对象。

        Args:
            raw: 从 YAML 加载的原始 dict

        Returns:
            QuickCheckConfig: 结构化的配置对象
        """
        quick_check = raw.get("quick_check", raw)

        # 解析采集开关
        collection = quick_check.get("collection", {})

        # 解析探测目标
        targets = quick_check.get("targets", {})

        # 解析 DNS 服务器
        dns_servers = targets.get("dns_servers", {})

        # 解析连通性目标
        connectivity = targets.get("connectivity", {})

        # 解析阈值
        thresholds_raw = quick_check.get("thresholds", {})

        return QuickCheckConfig(
            # 采集开关
            collection_adapters=collection.get("adapters", True),
            collection_routes=collection.get("routes", True),
            collection_dns=collection.get("dns", True),
            collection_proxy=collection.get("proxy", True),
            collection_firewall=collection.get("firewall", True),
            collection_arp=collection.get("arp", True),
            collection_ipv6=collection.get("ipv6", True),
            # DNS 服务器
            domestic_dns_servers=dns_servers.get("domestic", [
                "114.114.114.114",
                "223.5.5.5",
            ]),
            international_dns_servers=dns_servers.get("international", [
                "8.8.8.8",
                "1.1.1.1",
            ]),
            # 连通性目标
            domestic_targets=self._parse_targets(
                connectivity.get("domestic", [])
            ),
            international_targets=self._parse_targets(
                connectivity.get("international", [])
            ),
            # DNS 分流测试域名
            dns_split_domains=targets.get("dns_split_domains", [
                "www.google.com",
                "www.baidu.com",
                "github.com",
            ]),
            # 阈值
            thresholds=ThresholdConfig(
                gateway_rtt_warning_ms=thresholds_raw.get(
                    "gateway_rtt_warning_ms", 100
                ),
                gateway_loss_warning_pct=thresholds_raw.get(
                    "gateway_loss_warning_pct", 5
                ),
                dns_timeout_ms=thresholds_raw.get("dns_timeout_ms", 2000),
                dns_slow_ms=thresholds_raw.get("dns_slow_ms", 500),
                international_loss_warning_pct=thresholds_raw.get(
                    "international_loss_warning_pct", 10
                ),
            ),
            # 并发控制
            max_concurrent_probes=quick_check.get("max_concurrent_probes", 5),
            max_concurrent_dns_queries=quick_check.get(
                "max_concurrent_dns_queries", 3
            ),
            probe_interval=quick_check.get("probe_interval", 0.5),
            # 元信息
            config_version=quick_check.get("config_version", "1.0.0"),
        )

    def _parse_targets(
        self, targets_raw: List[Dict[str, Any]]
    ) -> List[ProbeTargetConfig]:
        """解析探测目标列表

        Args:
            targets_raw: 原始目标配置列表

        Returns:
            List[ProbeTargetConfig]: 结构化的目标配置列表
        """
        return [
            ProbeTargetConfig(
                host=item.get("host", ""),
                type=item.get("type", "icmp"),
            )
            for item in targets_raw
        ]

    def reload(self) -> QuickCheckConfig:
        """重新加载配置文件

        Returns:
            QuickCheckConfig: 重新加载后的配置对象
        """
        return self.load()
