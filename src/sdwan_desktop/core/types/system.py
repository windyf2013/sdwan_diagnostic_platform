"""
系统信息类型定义

遵循 SDWAN_SPEC.md §2.1.1 数据结构规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from .base import BaseContract


class AdapterStatus(str, Enum):
    """网卡状态枚举"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class AdapterType(str, Enum):
    """网卡类型枚举"""
    ETHERNET = "ethernet"
    WIFI = "wifi"
    LOOPBACK = "loopback"
    TUNNEL = "tunnel"
    VIRTUAL = "virtual"
    OTHER = "other"


@dataclass(slots=True)
class AdapterInfo(BaseContract):
    """网卡信息"""
    name: str = ""
    description: str = ""
    mac_address: str = ""
    adapter_type: AdapterType = AdapterType.ETHERNET
    status: AdapterStatus = AdapterStatus.UNKNOWN
    is_connected: bool = False
    speed_mbps: Optional[int] = None
    ip_addresses: List[str] = field(default_factory=list)
    ip_subnets: List[str] = field(default_factory=list)
    default_gateway: Optional[str] = None
    dhcp_enabled: bool = False
    dns_servers: List[str] = field(default_factory=list)
    dns_suffix: Optional[str] = None
    mtu: int = 1500
    physical_address: Optional[str] = None
    manufacturer: Optional[str] = None
    driver_version: Optional[str] = None


@dataclass(slots=True)
class IpConfigInfo(BaseContract):
    """IP配置信息"""
    ip_address: str = ""
    subnet_mask: str = ""
    default_gateway: Optional[str] = None
    dhcp_enabled: bool = False
    dns_servers: List[str] = field(default_factory=list)
    dns_suffix: Optional[str] = None
    dhcp_server: Optional[str] = None
    dhcp_lease_obtained: Optional[str] = None
    dhcp_lease_expires: Optional[str] = None
    wins_primary: Optional[str] = None
    wins_secondary: Optional[str] = None
    
    @property
    def all_addresses(self) -> List[str]:
        """获取所有IP地址（包括IPv6）"""
        # 这里可以扩展支持IPv6
        return [self.ip_address]


@dataclass(slots=True)
class RouteInfo(BaseContract):
    """路由表条目"""
    destination: str = ""
    netmask: str = ""
    gateway: str = ""
    interface: str = ""
    metric: int = 0
    protocol: str = "static"  # static, dynamic, local, etc.
    persistent: bool = False
    
    @property
    def is_default_route(self) -> bool:
        """是否为默认路由"""
        return self.destination == "0.0.0.0" and self.netmask == "0.0.0.0"


@dataclass(slots=True)
class DnsConfigInfo(BaseContract):
    """DNS配置信息"""
    servers: List[str] = field(default_factory=list)
    suffix_search_order: List[str] = field(default_factory=list)
    primary_dns_suffix: Optional[str] = None
    connection_specific_suffix: Optional[str] = None
    registration_enabled: bool = True
    dynamic_update_enabled: bool = True


@dataclass(slots=True)
class ProxyConfigInfo(BaseContract):
    """代理配置信息"""
    enabled: bool = False
    server: Optional[str] = None
    bypass_list: List[str] = field(default_factory=list)
    auto_config_url: Optional[str] = None
    auto_detect_enabled: bool = False


@dataclass(slots=True)
class FirewallInfo(BaseContract):
    """防火墙状态信息"""
    enabled: bool = False
    inbound_blocked: bool = False
    outbound_blocked: bool = False
    profiles: Dict[str, bool] = field(default_factory=dict)  # domain, private, public
    icmp_blocked: bool = False
    rules_count: int = 0


@dataclass(slots=True)
class ArpEntry(BaseContract):
    """ARP表条目"""
    ip_address: str = ""
    mac_address: str = ""
    interface: str = ""
    type: str = "dynamic"  # dynamic, static, invalid


@dataclass(slots=True)
class ConnectionInfo(BaseContract):
    """活动连接信息"""
    protocol: str = "tcp"  # tcp, udp
    local_address: str = ""
    local_port: int = 0
    remote_address: str = ""
    remote_port: int = 0
    state: str = "UNKNOWN"  # LISTEN, ESTABLISHED, TIME_WAIT, etc.
    pid: Optional[int] = None
    process_name: Optional[str] = None


@dataclass(slots=True)
class Ipv6Info(BaseContract):
    """IPv6配置信息"""
    enabled: bool = False
    addresses: List[str] = field(default_factory=list)
    default_gateway: Optional[str] = None
    dns_servers: List[str] = field(default_factory=list)
    is_preferred: bool = False


@dataclass(slots=True)
class SystemInfoSnapshot(BaseContract):
    """系统信息快照 - 一键体检采集的全部信息"""
    
    # 1. 网卡配置信息
    adapters: List[AdapterInfo] = field(default_factory=list)
    
    # 2. IP配置信息
    ip_config: Optional[IpConfigInfo] = None
    
    # 3. 路由表信息
    routes: List[RouteInfo] = field(default_factory=list)
    
    # 4. DNS配置
    dns_config: Optional[DnsConfigInfo] = None
    
    # 5. 代理配置
    proxy_config: Optional[ProxyConfigInfo] = None
    
    # 6. 防火墙状态
    firewall_status: Optional[FirewallInfo] = None
    
    # 7. ARP表
    arp_table: List[ArpEntry] = field(default_factory=list)
    
    # 8. 活动连接
    active_connections: List[ConnectionInfo] = field(default_factory=list)
    
    # 9. IPv6信息
    ipv6: Optional[Ipv6Info] = None
    
    # 10. 系统信息
    hostname: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    uptime_seconds: Optional[int] = None
    
    @property
    def primary_adapter(self) -> Optional[AdapterInfo]:
        """获取主网卡（有默认网关的网卡）"""
        if not self.adapters:
            return None
        
        # 优先查找有默认网关的网卡
        for adapter in self.adapters:
            if adapter.default_gateway and adapter.is_connected:
                return adapter
        
        # 其次查找已连接的网卡
        for adapter in self.adapters:
            if adapter.is_connected:
                return adapter
        
        return self.adapters[0] if self.adapters else None
    
    @property
    def default_route(self) -> Optional[RouteInfo]:
        """获取默认路由"""
        for route in self.routes:
            if route.is_default_route:
                return route
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            "adapters": [adapter.to_json_dict() for adapter in self.adapters],
            "ip_config": self.ip_config.to_json_dict() if self.ip_config else None,
            "routes": [route.to_json_dict() for route in self.routes],
            "dns_config": self.dns_config.to_json_dict() if self.dns_config else None,
            "proxy_config": self.proxy_config.to_json_dict() if self.proxy_config else None,
            "firewall_status": self.firewall_status.to_json_dict() if self.firewall_status else None,
            "arp_table": [arp.to_json_dict() for arp in self.arp_table],
            "active_connections": [conn.to_json_dict() for conn in self.active_connections],
            "ipv6": self.ipv6.to_json_dict() if self.ipv6 else None,
            "hostname": self.hostname,
            "os_version": self.os_version,
            "architecture": self.architecture,
            "uptime_seconds": self.uptime_seconds,
            "id": self.id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
        }