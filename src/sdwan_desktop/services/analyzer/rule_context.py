"""
规则评估上下文 - 聚合所有检测结果供规则引擎使用

遵循 SDWAN_SPEC.md §2.1 数据结构规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from sdwan_desktop.core.types.system import (
    AdapterInfo,
    DnsConfigInfo,
    FirewallInfo,
    IpConfigInfo,
    Ipv6Info,
    ProxyConfigInfo,
    RouteInfo,
    SystemInfoSnapshot,
)
from sdwan_desktop.services.connectivity import ConnectivityTestResult
from sdwan_desktop.services.dns_split import DnsSplitTestResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class QuickCheckContext:
    """一键体检规则评估上下文

    聚合系统采集信息、连通性测试结果、DNS分流测试结果，
    供规则引擎中的各条规则进行评估。
    """

    # ==================== 系统采集信息 ====================

    system_info: SystemInfoSnapshot
    """系统信息快照（包含网卡、IP、路由、DNS、代理、防火墙等）"""

    # ==================== 探测结果 ====================

    connectivity: ConnectivityTestResult
    """连通性测试结果（网关、DNS、国内外目标）"""

    dns_split: DnsSplitTestResult
    """DNS分流测试结果"""

    # ==================== 便捷属性 ====================

    @property
    def primary_adapter(self) -> Optional[AdapterInfo]:
        """获取主网卡"""
        return self.system_info.primary_adapter

    @property
    def ip_config(self) -> Optional[IpConfigInfo]:
        """获取IP配置"""
        return self.system_info.ip_config

    @property
    def routes(self) -> List[RouteInfo]:
        """获取路由表"""
        return self.system_info.routes

    @property
    def dns_config(self) -> Optional[DnsConfigInfo]:
        """获取DNS配置"""
        return self.system_info.dns_config

    @property
    def proxy_config(self) -> Optional[ProxyConfigInfo]:
        """获取代理配置"""
        return self.system_info.proxy_config

    @property
    def firewall_status(self) -> Optional[FirewallInfo]:
        """获取防火墙状态"""
        return self.system_info.firewall_status

    @property
    def arp_table(self) -> List:
        """获取ARP表"""
        return self.system_info.arp_table

    @property
    def ipv6(self) -> Optional[Ipv6Info]:
        """获取IPv6信息"""
        return self.system_info.ipv6

    @property
    def gateway_ping(self):
        """获取网关Ping结果"""
        return self.connectivity.gateway_ping

    @property
    def domestic_dns_results(self):
        """获取国内DNS探测结果"""
        return self.connectivity.domestic_dns_results

    @property
    def international_dns_results(self):
        """获取国际DNS探测结果"""
        return self.connectivity.international_dns_results

    @property
    def domestic_target_results(self):
        """获取国内目标探测结果"""
        return self.connectivity.domestic_target_results

    @property
    def international_target_results(self):
        """获取国际目标探测结果"""
        return self.connectivity.international_target_results

    @property
    def domestic_success_rate(self) -> float:
        """国内目标成功率"""
        return self.connectivity.domestic_success_rate

    @property
    def international_success_rate(self) -> float:
        """国际目标成功率"""
        return self.connectivity.international_success_rate

    @property
    def default_route(self):
        """获取默认路由"""
        return self.system_info.default_route

    @property
    def default_routes(self) -> List[RouteInfo]:
        """获取所有默认路由"""
        return [r for r in self.system_info.routes if r.is_default_route]

    @property
    def has_dns_split_anomaly(self) -> bool:
        """是否存在DNS分流异常"""
        if self.dns_split is None:
            return False
        return self.dns_split.split_count > 0
    
    @property
    def dns_split_domains(self):
        """获取DNS分流测试的域名结果"""
        if self.dns_split is None:
            return []
        return self.dns_split.domain_results
