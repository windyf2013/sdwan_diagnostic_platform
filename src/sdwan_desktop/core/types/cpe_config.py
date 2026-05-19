"""
CPE配置类型定义

遵循 SDWAN_SPEC.md §2.1 数据结构规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from .base import BaseContract


_RAISECOM_STYLE_WAN_IFACE = re.compile(r"^(ge|xge)\d+$", re.IGNORECASE)


@dataclass(slots=True)
class InterfaceInfo(BaseContract):
    """接口信息"""
    name: str = ""
    """接口名称"""
    ip_address: Optional[str] = None
    """IP地址"""
    status: str = "unknown"
    """接口状态: up/down/unknown"""
    mtu: int = 1500
    """MTU值"""
    mac_address: Optional[str] = None
    """MAC地址"""
    description: Optional[str] = None
    """接口描述"""
    speed_mbps: Optional[int] = None
    """接口速度(Mbps)"""
    raw_block: Optional[str] = None
    """原始输出块(用于调试)"""


@dataclass(slots=True)
class RouteEntry(BaseContract):
    """路由条目"""
    destination: str = ""
    """目标网络"""
    gateway: Optional[str] = None
    """下一跳网关"""
    interface: Optional[str] = None
    """出接口"""
    metric: int = 0
    """路由度量值"""
    protocol: str = "unknown"
    """路由协议: connected/static/bgp/ospf等"""
    raw_line: Optional[str] = None
    """原始行(用于调试)"""


@dataclass(slots=True)
class SdwanPolicy(BaseContract):
    """SD-WAN策略"""
    name: str = ""
    """策略名称"""
    source: str = "any"
    """源地址"""
    destination: str = "any"
    """目的地址"""
    application: str = "any"
    """应用列表"""
    sla_class: Optional[str] = None
    """SLA等级"""
    preferred_path: Optional[str] = None
    """首选路径"""
    backup_path: Optional[str] = None
    """备份路径"""
    raw_block: Optional[str] = None
    """原始输出块(用于调试)"""


@dataclass(slots=True)
class VpnTunnelInfo(BaseContract):
    """VPN隧道信息"""
    remote_ip: str = ""
    """对端IP"""
    local_color: str = ""
    """本地颜色标识"""
    remote_color: str = ""
    """远端颜色标识"""
    state: str = "unknown"
    """隧道状态: up/down/unknown"""
    type: str = "ipsec"
    """隧道类型: ipsec/gre等"""
    uptime_seconds: Optional[int] = None
    """运行时长(秒)"""
    raw_block: Optional[str] = None
    """running-config 等原始片段(用于报告证据链)"""


@dataclass(slots=True)
class CpeArpEntry:
    """CPE ARP 表项（厂商解析后统一模型，用于 PC↔CPE 邻接推断）。"""

    ip_address: str = ""
    mac_address: str = ""
    interface: str = ""
    state: str = ""
    raw_line: Optional[str] = None


@dataclass(slots=True)
class NatRuleInfo(BaseContract):
    """NAT规则信息"""
    protocol: str = ""
    """协议: tcp/udp/icmp"""
    inside_addr: str = ""
    """内部地址"""
    outside_addr: str = ""
    """外部地址"""
    nat_type: str = "dynamic"
    """NAT类型: static/dynamic"""
    raw_line: Optional[str] = None
    """原始行(用于调试)"""


@dataclass(slots=True)
class CpeConfiguration(BaseContract):
    """CPE配置解析结果 - 标准化模型
    
    聚合从CPE设备采集并解析的所有配置信息，
    提供标准化的访问接口和派生属性。
    """
    
    # ==================== 设备信息 ====================
    vendor: str = ""
    """厂商名称: cisco_sdwan/huawei/fortinet等"""
    model: str = ""
    """设备型号"""
    version: str = ""
    """软件版本"""
    hostname: str = ""
    """主机名"""
    
    # ==================== 配置数据 ====================
    interfaces: List[InterfaceInfo] = field(default_factory=list)
    """接口列表"""
    routes: List[RouteEntry] = field(default_factory=list)
    """路由表"""
    sdwan_policies: List[SdwanPolicy] = field(default_factory=list)
    """SD-WAN策略列表"""
    vpn_tunnels: List[VpnTunnelInfo] = field(default_factory=list)
    """VPN隧道列表"""
    nat_rules: List[NatRuleInfo] = field(default_factory=list)
    """NAT规则列表"""
    arp_entries: List[CpeArpEntry] = field(default_factory=list)
    """ARP 表（用于与 PC 侧 ARP 交叉验证三层邻接）"""
    
    # ==================== 调试信息 ====================
    raw_outputs: Dict[str, str] = field(default_factory=dict)
    """原始命令输出(仅用于调试，不进入报告)"""
    
    # ==================== 派生属性 ====================
    
    @property
    def wan_interfaces(self) -> List[InterfaceInfo]:
        """获取WAN口列表
        
        根据接口名称模式识别WAN口:
        - ge0/, eth0, wan, GigabitEthernet0/ 等
        """
        wan_patterns = ["ge0/", "eth0", "wan", "gigabitethernet0/"]
        return [
            iface for iface in self.interfaces
            if any(p in iface.name.lower() for p in wan_patterns)
            or _RAISECOM_STYLE_WAN_IFACE.match((iface.name or "").strip())
        ]
    
    @property
    def lan_interfaces(self) -> List[InterfaceInfo]:
        """获取LAN口列表
        
        根据接口名称模式识别LAN口:
        - ge0/1, eth1, lan, Vlan 等
        """
        lan_patterns = ["ge0/1", "eth1", "lan", "vlan"]
        return [
            iface
            for iface in self.interfaces
            if "management" not in (iface.name or "").lower()
            and any(p in iface.name.lower() for p in lan_patterns)
        ]
    
    @property
    def default_route(self) -> Optional[RouteEntry]:
        """获取默认路由
        
        查找目标为 0.0.0.0/0 或 default 的路由条目
        """
        for route in self.routes:
            if route.destination in ["0.0.0.0/0", "default"]:
                return route
        return None
    
    @property
    def tunnel_status_summary(self) -> Dict[str, int]:
        """隧道状态汇总
        
        Returns:
            字典，包含 up/down/unknown 三种状态的隧道数量
        """
        summary = {"up": 0, "down": 0, "unknown": 0}
        for tunnel in self.vpn_tunnels:
            state = tunnel.state.lower()
            if state in summary:
                summary[state] += 1
            else:
                summary["unknown"] += 1
        return summary
    
    def get_interface_by_ip(self, ip: str) -> Optional[InterfaceInfo]:
        """根据IP地址查找接口
        
        Args:
            ip: IP地址
            
        Returns:
            匹配的接口信息，未找到返回None
        """
        for iface in self.interfaces:
            if iface.ip_address == ip:
                return iface
        return None
    
    def get_routes_to(self, destination: str) -> List[RouteEntry]:
        """获取到目标网络的路由
        
        TODO: 实现最长前缀匹配算法
        
        Args:
            destination: 目标IP或网段
            
        Returns:
            匹配的路由列表
        """
        # 简化实现：直接匹配目标
        return [route for route in self.routes if route.destination == destination]
