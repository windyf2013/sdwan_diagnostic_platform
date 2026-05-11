"""
RAISECOM MSG5200A 配置解析器

实现 RAISECOM（瑞斯康达）MSG5200A 系列 SD-WAN CPE 设备的配置解析。
支持 RCIOS 4.23 及以上版本。

遵循 SDWAN_SPEC.md §2.4 工具系统规范
遵循 detail_function_design.md §2.2 厂商解析器实现示例
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sdwan_desktop.core.types.cpe_config import (
    CpeConfiguration,
    InterfaceInfo,
    NatRuleInfo,
    RouteEntry,
    SdwanPolicy,
    VpnTunnelInfo,
)
from sdwan_desktop.services.parser.vendor import VendorConfigParser

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RaisecomUserInfo:
    """RAISECOM 用户信息"""
    username: str = ""
    role: str = ""
    auth_table: str = ""
    privilege_level: int = 0
    raw_line: Optional[str] = None


@dataclass(slots=True)
class RaisecomViewInfo:
    """RAISECOM 视图信息"""
    view_name: str = ""
    prompt_pattern: str = ""
    requires_password: bool = False
    description: str = ""


@dataclass(slots=True)
class RaisecomSystemInfo:
    """RAISECOM 系统详细信息"""
    product_series: str = ""
    compile_time: str = ""
    device_uptime: str = ""
    batch_number: str = ""
    customer: str = ""
    sub_customer: str = ""
    serial_number: str = ""
    system_loid: str = ""
    active_image: str = ""
    system_mac: str = ""
    bootrom_version: str = ""
    pv_version: str = ""
    pcb_version: str = ""
    bom_version: str = ""
    wlan_2g_card: str = ""
    wlan_5g_card: str = ""
    user_behavior_control: str = ""
    current_time: str = ""
    system_runtime: str = ""
    cpu_usage_total: str = ""
    cpu_usage_per_core: Dict[str, str] = field(default_factory=dict)
    memory_usage: str = ""


@dataclass(slots=True)
class RaisecomDnsInfo:
    """RAISECOM DNS 配置信息"""
    interface: str = ""
    master_dns: Optional[str] = None
    backup_dns: Optional[str] = None


@dataclass(slots=True)
class RaisecomArpEntry:
    """RAISECOM ARP 表项"""
    ip_address: str = ""
    mac_address: str = ""
    entry_type: str = ""  # S-Static, D-Dynamic, P-Proxy
    hw_type: str = ""
    state: str = ""  # R-Reachable, S-Stale, D-Delay, P-Probe
    interface: str = ""
    aging: int = 0
    raw_line: Optional[str] = None


@dataclass(slots=True)
class RaisecomCallhomeInfo:
    """RAISECOM Callhome 配置"""
    endpoint_name: str = ""
    current_link: str = ""
    auth_type: str = ""
    ip_address: str = ""
    port: int = 0
    ifname: str = ""
    connect_status: str = ""


@dataclass(slots=True)
class RaisecomL2tpGroup:
    """RAISECOM L2TP 组配置"""
    group_name: str = ""
    username: str = ""
    peer_address: str = ""
    peer_port: int = 1701
    tunnel_name: str = ""
    bind_if_num: int = 0
    keepalive_timeout: int = 60
    auto_dial_interval: int = 5
    auto_dial_times: int = 3
    dial_on_start: bool = True
    raw_block: Optional[str] = None


@dataclass(slots=True)
class RaisecomUrlGroup:
    """RAISECOM URL 组详细配置"""
    group_name: str = ""
    aging_time: int = 3600
    dns_server: Optional[str] = None
    nexthop_master: Optional[str] = None
    source_ip: Optional[str] = None
    security_ip_enabled: bool = False
    security_ips: List[str] = field(default_factory=list)
    enabled: bool = False
    url_match_mode: str = "suffix"
    priority: int = 20
    domains: List[str] = field(default_factory=list)
    fwmark: Optional[str] = None  # 从 ip rule 推断
    raw_block: Optional[str] = None


class RaisecomMsg5200Parser(VendorConfigParser):
    """RAISECOM MSG5200A 系列配置解析器
    
    支持解析 RAISECOM MSG5200A 系列设备：
    - MSG5200-GEC-8E-G4 等型号
    - RCIOS 4.23 及以上版本
    
    通过正则表达式解析 show version all / show running-config / 
    show interface 等命令输出。
    """
    
    def __init__(self):
        """初始化解析器，存储扩展解析结果"""
        self.users: List[RaisecomUserInfo] = []
        self.views: List[RaisecomViewInfo] = []
        self.system_info: Optional[RaisecomSystemInfo] = None
        self.dns_configs: List[RaisecomDnsInfo] = []
        self.arp_entries: List[RaisecomArpEntry] = []
        self.callhome: Optional[RaisecomCallhomeInfo] = None
        self.l2tp_groups: List[RaisecomL2tpGroup] = []
        self.url_groups_detail: List[RaisecomUrlGroup] = []
        self.ip_rules: List[Dict] = []
        self.policy_routes: Dict[str, List[RouteEntry]] = {}
    
    def get_vendor_name(self) -> str:
        """返回厂商名称标识"""
        return "raisecom_msg5200"
    
    def detect_vendor(self, raw_output: str) -> bool:
        """检测是否为 RAISECOM MSG5200A 设备
        
        通过检测版本输出中的特征字符串来识别设备。
        
        Args:
            raw_output: 设备命令输出（通常是 show version all）
            
        Returns:
            True 如果检测到是 RAISECOM MSG5200A 设备
        """
        if not raw_output:
            return False
        
        indicators = [
            "rcios",
            "msg5200",
            "raisecom",
        ]
        
        output_lower = raw_output.lower()
        return any(ind in output_lower for ind in indicators)
    
    def parse_version(self, raw_output: str) -> str:
        """解析软件版本
        
        支持的格式：
        - RCIOS version   : 4.23.387.20250805
        
        Args:
            raw_output: show version all 命令输出
            
        Returns:
            版本号字符串，如 "4.23.387.20250805"，失败返回 "unknown"
        """
        if not raw_output:
            return "unknown"
        
        # 匹配 RCIOS version 行
        match = re.search(r"RCIOS version\s*:\s*(\S+)", raw_output, re.IGNORECASE)
        if match:
            return match.group(1)
        
        logger.warning("无法解析 RAISECOM 版本信息")
        return "unknown"
    
    def _detect_model(self, raw_output: str) -> str:
        """检测设备型号
        
        Args:
            raw_output: show version all 命令输出
            
        Returns:
            设备型号字符串，如 "MSG5200-GEC-8E-G4"，失败返回 "unknown"
        """
        if not raw_output:
            return "unknown"
        
        # 匹配 PN (Part Number) 行
        match = re.search(r"PN\s*:\s*(\S+(?:-\S+)*)", raw_output, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # 备选：匹配 Product series
        match = re.search(r"Product series\s*:\s*(\S+)", raw_output, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return "unknown"
    
    def _detect_hostname(self, raw_output: str) -> str:
        """检测主机名
        
        Args:
            raw_output: show running-config 或 show version all 命令输出
            
        Returns:
            主机名字符串，失败返回 "unknown"
        """
        if not raw_output:
            return "unknown"
        
        # 从 hostname 配置行提取
        match = re.search(r"^hostname\s+(\S+)", raw_output, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1)
        
        # 从 prompt 提取（备选方案）
        match = re.search(r"([a-zA-Z0-9_-]+)#", raw_output)
        if match:
            return match.group(1)
        
        return "unknown"
    
    def parse_system_info(self, raw_output: str) -> Optional[RaisecomSystemInfo]:
        """解析系统详细信息
        
        Args:
            raw_output: show version all 命令输出
            
        Returns:
            RaisecomSystemInfo 对象
        """
        if not raw_output:
            return None
        
        info = RaisecomSystemInfo()
        
        # 提取 Product series
        match = re.search(r"Product series\s*:\s*(.+)", raw_output)
        if match:
            info.product_series = match.group(1).strip()
        
        # 提取 Compile time
        match = re.search(r"Compile time\s*:\s*(.+)", raw_output)
        if match:
            info.compile_time = match.group(1).strip()
        
        # 提取 Device uptime
        match = re.search(r"Device uptime\s*:\s*(.+)", raw_output)
        if match:
            info.device_uptime = match.group(1).strip()
        
        # 提取 Batch Number
        match = re.search(r"Batch Number\s*:\s*(.+)", raw_output)
        if match:
            info.batch_number = match.group(1).strip()
        
        # 提取 Customer
        match = re.search(r"Customer\s*:\s*(.+)", raw_output)
        if match:
            info.customer = match.group(1).strip()
        
        # 提取 SubCustomer
        match = re.search(r"SubCustomer\s*:\s*(.+)", raw_output)
        if match:
            info.sub_customer = match.group(1).strip()
        
        # 提取 Serial Number
        match = re.search(r"Serial Number\s*:\s*(.+)", raw_output)
        if match:
            info.serial_number = match.group(1).strip()
        
        # 提取 System Loid
        match = re.search(r"System Loid\s*:\s*(.+)", raw_output)
        if match:
            info.system_loid = match.group(1).strip()
        
        # 提取 Active image
        match = re.search(r"Active image\s*:\s*(.+)", raw_output)
        if match:
            info.active_image = match.group(1).strip()
        
        # 提取 RCIOS version
        match = re.search(r"RCIOS version\s*:\s*(.+)", raw_output)
        if match:
            # version 已经在 parse_version 中处理，这里不需要额外操作
            pass
        
        # 提取 System MAC
        match = re.search(r"System MAC\s*:\s*(.+)", raw_output)
        if match:
            info.system_mac = match.group(1).strip()
        
        # 提取 Bootrom version
        match = re.search(r"Bootrom version\s*:\s*(.+)", raw_output)
        if match:
            info.bootrom_version = match.group(1).strip()
        
        # 提取 PV
        match = re.search(r"PV\s*:\s*(.+)", raw_output)
        if match:
            info.pv_version = match.group(1).strip()
        
        # 提取 PCB Version
        match = re.search(r"PCB Version\s*:\s*(.+)", raw_output)
        if match:
            info.pcb_version = match.group(1).strip()
        
        # 提取 BOM Version
        match = re.search(r"BOM Version\s*:\s*(.+)", raw_output)
        if match:
            info.bom_version = match.group(1).strip()
        
        # 提取 2.4G WLAN Card
        match = re.search(r"2\.4G WLAN Card\s*:\s*(.+)", raw_output)
        if match:
            info.wlan_2g_card = match.group(1).strip()
        
        # 提取 5G WLAN Card
        match = re.search(r"5G WLAN Card\s*:\s*(.+)", raw_output)
        if match:
            info.wlan_5g_card = match.group(1).strip()
        
        # 提取 UserBehaviorControl
        match = re.search(r"UserBehaviorControl\s*:\s*(.+)", raw_output)
        if match:
            info.user_behavior_control = match.group(1).strip()
        
        self.system_info = info
        return info
    
    def parse_cpu_memory_info(self, cpu_output: str, mem_output: str, uptime_output: str):
        """解析 CPU、内存和运行时间信息
        
        Args:
            cpu_output: show cpu usage 输出
            mem_output: show memory usage 输出
            uptime_output: show system uptime 输出
        """
        if not self.system_info:
            self.system_info = RaisecomSystemInfo()
        
        # 解析 CPU 使用率
        if cpu_output:
            match = re.search(r"Total CPU Usage\s*:\s*(\d+)%", cpu_output)
            if match:
                self.system_info.cpu_usage_total = f"{match.group(1)}%"
            
            # 解析每个核心的使用率
            for match in re.finditer(r"(CPU\d+)\s+Usage\s*:\s*(\d+)%", cpu_output):
                self.system_info.cpu_usage_per_core[match.group(1)] = f"{match.group(2)}%"
        
        # 解析内存使用率
        if mem_output:
            match = re.search(r"MemUsage\s*:\s*([\d.]+)%", mem_output)
            if match:
                self.system_info.memory_usage = f"{match.group(1)}%"
        
        # 解析系统时间
        if uptime_output:
            match = re.search(r"current time\s*:\s*(.+)", uptime_output)
            if match:
                self.system_info.current_time = match.group(1).strip()
            
            match = re.search(r"system runtime\s*:\s*(.+)", uptime_output)
            if match:
                self.system_info.system_runtime = match.group(1).strip()
    
    def parse_users(self, raw_output: str) -> List[RaisecomUserInfo]:
        """解析用户配置信息
        
        Args:
            raw_output: show running-config 输出
            
        Returns:
            用户信息列表
        """
        users = []
        
        if not raw_output:
            return users
        
        # 解析 user 配置行
        # 格式：user administrator CMCCAdmin local secret <encrypted> authorized-table telecomadmin 1
        user_pattern = r"^user\s+(\S+)\s+(\S+)\s+(\S+)\s+secret\s+(\S+)\s+authorized-table\s+(\S+)\s+(\d+)"
        
        for match in re.finditer(user_pattern, raw_output, re.MULTILINE):
            user = RaisecomUserInfo(
                username=match.group(2),  # 第二个字段是实际用户名
                role=match.group(1),  # 第一个字段是角色
                auth_table=match.group(5),
                privilege_level=int(match.group(6)),
                raw_line=match.group(0)
            )
            users.append(user)
        
        self.users = users
        logger.info(f"成功解析 {len(users)} 个用户配置")
        return users
    
    def parse_views(self, raw_output: str) -> List[RaisecomViewInfo]:
        """解析视图信息（从命令提示符和注释中推断）
        
        Args:
            raw_output: 完整的命令交互输出（包含提示符）
            
        Returns:
            视图信息列表
        """
        views = []
        
        if not raw_output:
            return views
        
        # 识别不同的视图模式
        view_patterns = [
            (r"host>\s*enable", "user_exec", "host>", False, "用户EXEC视图"),
            (r"host#\s*$", "privileged_exec", "host#", False, "特权EXEC视图"),
            (r"host\(test-node\)#", "test_node", "host(test-node)#", True, "测试节点视图"),
            (r"host\(config\)#", "config", "host(config)#", False, "全局配置视图"),
            (r"host\(config-netconf\)#", "config_netconf", "host(config-netconf)#", False, "Netconf配置视图"),
            (r"bash-4\.3#", "diagnose", "bash-4.3#", True, "诊断视图（Linux bash）"),
        ]
        
        for pattern, name, prompt, needs_pwd, desc in view_patterns:
            if re.search(pattern, raw_output, re.MULTILINE):
                view = RaisecomViewInfo(
                    view_name=name,
                    prompt_pattern=prompt,
                    requires_password=needs_pwd,
                    description=desc
                )
                views.append(view)
        
        self.views = views
        logger.info(f"成功识别 {len(views)} 个视图模式")
        return views
    
    def parse_dns_configs(self, raw_output: str) -> List[RaisecomDnsInfo]:
        """解析 DNS 配置
        
        Args:
            raw_output: show dns active 输出
            
        Returns:
            DNS 配置列表
        """
        dns_configs = []
        
        if not raw_output:
            return dns_configs
        
        # 解析格式：
        # ge1:
        # ip name-server master  202.106.46.151
        # ip name-server backup  8.8.8.8
        
        lines = raw_output.strip().split('\n')
        current_interface = None
        
        for line in lines:
            # 检测接口行
            iface_match = re.match(r"^(\w+\d+):\s*$", line)
            if iface_match:
                current_interface = iface_match.group(1)
                continue
            
            if current_interface:
                # 解析 master DNS
                master_match = re.search(r"ip name-server master\s+(\S+)", line)
                if master_match:
                    dns = RaisecomDnsInfo(
                        interface=current_interface,
                        master_dns=master_match.group(1)
                    )
                    dns_configs.append(dns)
                
                # 解析 backup DNS
                backup_match = re.search(r"ip name-server backup\s+(\S+)", line)
                if backup_match:
                    # 如果已有该接口的 DNS 配置，更新 backup
                    if dns_configs and dns_configs[-1].interface == current_interface:
                        dns_configs[-1].backup_dns = backup_match.group(1)
                    else:
                        dns = RaisecomDnsInfo(
                            interface=current_interface,
                            backup_dns=backup_match.group(1)
                        )
                        dns_configs.append(dns)
        
        self.dns_configs = dns_configs
        logger.info(f"成功解析 {len(dns_configs)} 个接口的 DNS 配置")
        return dns_configs
    
    def parse_arp_table(self, raw_output: str) -> List[RaisecomArpEntry]:
        """解析 ARP 表
        
        Args:
            raw_output: show arp 输出
            
        Returns:
            ARP 表项列表
        """
        entries = []
        
        if not raw_output:
            return entries
        
        # 跳过表头
        lines = raw_output.strip().split('\n')
        for line in lines:
            # 跳过空行和表头
            if not line.strip() or line.startswith('Type:') or line.startswith('IP Address'):
                continue
            
            # 解析 ARP 条目
            # 格式：5.96.0.190       00:00:5e:20:82:a1      D     0x1      0x2    R      *     vxlan2500110    188    N/A
            parts = line.split()
            if len(parts) >= 10:
                try:
                    entry = RaisecomArpEntry(
                        ip_address=parts[0],
                        mac_address=parts[1],
                        entry_type=parts[2],
                        hw_type=parts[3],
                        state=parts[5],
                        interface=parts[7],
                        aging=int(parts[8]) if parts[8].isdigit() else 0,
                        raw_line=line
                    )
                    entries.append(entry)
                except (ValueError, IndexError) as e:
                    logger.warning(f"解析 ARP 条目失败: {line[:50]}... Error: {e}")
                    continue
        
        self.arp_entries = entries
        logger.info(f"成功解析 {len(entries)} 条 ARP 表项")
        return entries
    
    def parse_callhome(self, raw_output: str) -> Optional[RaisecomCallhomeInfo]:
        """解析 Callhome 配置
        
        Args:
            raw_output: show callhome all 输出
            
        Returns:
            Callhome 配置信息
        """
        if not raw_output:
            return None
        
        callhome = RaisecomCallhomeInfo()
        
        # 解析各字段
        match = re.search(r"endpoint name\s*:\s*(.+)", raw_output)
        if match:
            callhome.endpoint_name = match.group(1).strip()
        
        match = re.search(r"current link\s*:\s*(.+)", raw_output)
        if match:
            callhome.current_link = match.group(1).strip()
        
        match = re.search(r"auth type\s*:\s*(.+)", raw_output)
        if match:
            callhome.auth_type = match.group(1).strip()
        
        match = re.search(r"ip address\s*:\s*(.+)", raw_output)
        if match:
            callhome.ip_address = match.group(1).strip()
        
        match = re.search(r"port\s*:\s*(\d+)", raw_output)
        if match:
            callhome.port = int(match.group(1))
        
        match = re.search(r"ifname\s*:\s*(.*)", raw_output)
        if match:
            callhome.ifname = match.group(1).strip()
        
        match = re.search(r"connect status\s*:\s*(.+)", raw_output)
        if match:
            callhome.connect_status = match.group(1).strip()
        
        self.callhome = callhome
        logger.info(f"成功解析 Callhome 配置: {callhome.endpoint_name}")
        return callhome
    
    def parse_l2tp_groups(self, raw_output: str) -> List[RaisecomL2tpGroup]:
        """解析 L2TP 组配置
        
        Args:
            raw_output: show running-config 输出
            
        Returns:
            L2TP 组列表
        """
        groups = []
        
        if not raw_output:
            return groups
        
        # 解析 l2tp-group 配置块
        l2tp_pattern = r"l2tp-group\s+(\S+)\s*\n(.*?)(?=^l2tp-group|\Z)"
        
        for match in re.finditer(l2tp_pattern, raw_output, re.MULTILINE | re.DOTALL):
            group_name = match.group(1)
            block = match.group(2)
            
            try:
                group = RaisecomL2tpGroup(group_name=group_name, raw_block=block)
                
                # 提取 username
                uname_match = re.search(r"username\s+(\S+)", block)
                if uname_match:
                    group.username = uname_match.group(1)
                
                # 提取 peer-address
                peer_match = re.search(r"peer-address\s+(\S+)", block)
                if peer_match:
                    group.peer_address = peer_match.group(1)
                
                # 提取 peer-port
                port_match = re.search(r"peer-port\s+(\d+)", block)
                if port_match:
                    group.peer_port = int(port_match.group(1))
                
                # 提取 tunnel-name
                tunnel_match = re.search(r"tunnel-name\s+(\S+)", block)
                if tunnel_match:
                    group.tunnel_name = tunnel_match.group(1)
                
                # 提取 bind if_num
                bind_match = re.search(r"bind if_num\s+(\d+)", block)
                if bind_match:
                    group.bind_if_num = int(bind_match.group(1))
                
                # 提取 keepalive timeout
                ka_match = re.search(r"keepalive timeout\s+(\d+)", block)
                if ka_match:
                    group.keepalive_timeout = int(ka_match.group(1))
                
                # 提取 auto-dial interval 和 times
                dial_match = re.search(r"auto-dial interval\s+(\d+)\s+times\s+(\d+)", block)
                if dial_match:
                    group.auto_dial_interval = int(dial_match.group(1))
                    group.auto_dial_times = int(dial_match.group(2))
                
                # 提取 dial_on_start
                if "dial_on_start enable" in block:
                    group.dial_on_start = True
                
                groups.append(group)
                
            except Exception as e:
                logger.warning(f"解析 L2TP 组 '{group_name}' 失败: {e}")
                continue
        
        self.l2tp_groups = groups
        logger.info(f"成功解析 {len(groups)} 个 L2TP 组")
        return groups
    
    def parse_url_groups_detail(self, config_output: str, security_ip_output: str) -> List[RaisecomUrlGroup]:
        """解析 URL 组详细配置（包括安全 IP）
        
        Args:
            config_output: show running-config 输出
            security_ip_output: show url-group all security-ip 输出
            
        Returns:
            URL 组详细配置列表
        """
        url_groups = []
        
        if not config_output:
            return url_groups
        
        # 首先解析 security-ip 映射
        security_ip_map: Dict[str, List[str]] = {}
        if security_ip_output:
            current_group = None
            for line in security_ip_output.split('\n'):
                # 检测新的 URL 组
                group_match = re.match(r"^url-group\s+(\S+)", line)
                if group_match:
                    current_group = group_match.group(1)
                    security_ip_map[current_group] = []
                    continue
                
                # 检测 IP 地址行
                ip_match = re.match(r"^\s*(\d+\.\d+\.\d+\.\d+)", line)
                if ip_match and current_group:
                    security_ip_map[current_group].append(ip_match.group(1))
        
        # 解析 url-group 配置块
        url_group_pattern = r"url-group\s+(\S+)\s*\n(.*?)^exit"
        matches = re.finditer(url_group_pattern, config_output, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            group_name = match.group(1)
            block = match.group(2)
            
            try:
                url_group = RaisecomUrlGroup(group_name=group_name, raw_block=block)
                
                # 提取 aging time
                aging_match = re.search(r"aging time\s+(\d+)", block)
                if aging_match:
                    url_group.aging_time = int(aging_match.group(1))
                
                # 提取 dns server
                dns_match = re.search(r"dns server\s+(\S+)", block)
                if dns_match:
                    url_group.dns_server = dns_match.group(1)
                
                # 提取 nexthop master
                nexthop_match = re.search(r"nexthop master\s+(\S+)", block)
                if nexthop_match:
                    url_group.nexthop_master = nexthop_match.group(1)
                
                # 提取 source ip
                src_match = re.search(r"source ip\s+(\S+)", block)
                if src_match:
                    url_group.source_ip = src_match.group(1)
                
                # 提取 security ip enable
                if "security ip enable" in block:
                    url_group.security_ip_enabled = True
                    # 添加对应的安全 IP 列表
                    if group_name in security_ip_map:
                        url_group.security_ips = security_ip_map[group_name]
                
                # 提取 enable 状态
                if re.search(r"^\s+enable\s*$", block, re.MULTILINE):
                    url_group.enabled = True
                
                # 提取 url match mode
                match_mode = re.search(r"url match\s+(\S+)", block)
                if match_mode:
                    url_group.url_match_mode = match_mode.group(1)
                
                # 提取 priority
                priority_match = re.search(r"priority\s+(\d+)", block)
                if priority_match:
                    url_group.priority = int(priority_match.group(1))
                
                # 提取域名列表
                domains = re.findall(r"domain name\s+(\S+)", block)
                url_group.domains = domains
                
                # 根据 nexthop 推断 fwmark（从 ip rule 对应关系）
                # table 99 -> fwmark 0x66, table 100 -> fwmark 0x67
                if url_group.nexthop_master:
                    if "5.96.0.190" in url_group.nexthop_master:  # 跨境
                        url_group.fwmark = "0x66"
                    elif "6.96.0.190" in url_group.nexthop_master:  # 直播
                        url_group.fwmark = "0x67"
                
                url_groups.append(url_group)
                
            except Exception as e:
                logger.warning(f"解析 URL 组 '{group_name}' 失败: {e}")
                continue
        
        self.url_groups_detail = url_groups
        logger.info(f"成功解析 {len(url_groups)} 个 URL 组详细配置")
        return url_groups
    
    def parse_ip_rules(self, raw_output: str) -> List[Dict]:
        """解析策略路由规则（从 diagnose 视图的 ip rule show）
        
        Args:
            raw_output: ip rule show 输出
            
        Returns:
            策略路由规则列表
        """
        rules = []
        
        if not raw_output:
            return rules
        
        for line in raw_output.strip().split('\n'):
            if not line.strip():
                continue
            
            # 格式：32764:  from all fwmark 0x67 lookup 100
            match = re.search(r"(\d+):\s+from all(?:\s+fwmark\s+(0x[0-9a-fA-F]+))?\s+lookup\s+(\S+)", line)
            if match:
                rule = {
                    "priority": int(match.group(1)),
                    "fwmark": match.group(2),
                    "table": match.group(3),
                    "raw_line": line
                }
                rules.append(rule)
        
        self.ip_rules = rules
        logger.info(f"成功解析 {len(rules)} 条策略路由规则")
        return rules
    
    def parse_policy_routes(self, raw_output: str, table_id: str) -> List[RouteEntry]:
        """解析特定路由表的策略路由
        
        Args:
            raw_output: ip route show table <id> 输出
            table_id: 路由表 ID（99 或 100）
            
        Returns:
            路由条目列表
        """
        routes = []
        
        if not raw_output:
            return routes
        
        # 格式：default via 6.96.0.190 dev vxlan2510110
        for line in raw_output.strip().split('\n'):
            if not line.strip():
                continue
            
            match = re.search(r"default via\s+(\d+\.\d+\.\d+\.\d+)\s+dev\s+(\S+)", line)
            if match:
                route = RouteEntry(
                    id=f"policy_route_table{table_id}",
                    destination="0.0.0.0/0",
                    gateway=match.group(1),
                    interface=match.group(2),
                    metric=0,
                    protocol=f"policy_table_{table_id}",
                    raw_line=line
                )
                routes.append(route)
        
        self.policy_routes[f"table_{table_id}"] = routes
        logger.info(f"成功解析 table {table_id} 的 {len(routes)} 条策略路由")
        return routes
    
    def parse_interfaces(self, raw_output: str) -> List[InterfaceInfo]:
        """解析接口信息
        
        解析 show interface <name> 命令输出，提取接口名称、IP地址、状态、MTU等信息。
        注意：RAISECOM 设备需要为每个接口单独执行 show interface 命令。
        
        Args:
            raw_output: show interface 命令输出（单个接口的完整输出）
            
        Returns:
            InterfaceInfo 对象列表
        """
        interfaces = []
        
        if not raw_output:
            logger.warning("接口信息输出为空")
            return interfaces
        
        # RAISECOM 接口输出格式示例：
        # Interface vlan1 is up, Admin status is up 
        # aliasname vlan1
        # inet addr: 192.168.46.1 Bcast: 192.168.46.255 Mask:255.255.255.0
        # Hardware address: 08:23:45:67:21:32
        # UP BROADCAST PHYUP RUNNING MULTICAST  MTU:1500  Metric:1
        
        try:
            # 提取接口名称
            name_match = re.search(r"Interface\s+(\S+)\s+is", raw_output, re.IGNORECASE)
            if not name_match:
                logger.warning("无法提取接口名称")
                return interfaces
            
            name = name_match.group(1)
            
            # 提取状态
            status = "unknown"
            if "is up" in raw_output.lower():
                if "admin status is down" in raw_output.lower():
                    status = "down"
                else:
                    status = "up"
            elif "is down" in raw_output.lower():
                status = "down"
            
            # 提取 IP 地址
            ip_match = re.search(r"inet addr:\s*(\d+\.\d+\.\d+\.\d+)", raw_output)
            ip_address = ip_match.group(1) if ip_match else None
            
            # 提取 MAC 地址
            mac_match = re.search(r"Hardware address:\s*([0-9a-fA-F:]{17})", raw_output)
            mac_address = mac_match.group(1) if mac_match else None
            
            # 提取 MTU
            mtu_match = re.search(r"MTU:(\d+)", raw_output)
            mtu = int(mtu_match.group(1)) if mtu_match else 1500
            
            # 提取别名
            alias_match = re.search(r"aliasname\s+(\S+)", raw_output)
            description = alias_match.group(1) if alias_match else None
            
            # 提取速度（如果有）
            speed_match = re.search(r"current speed is (\d+)M", raw_output)
            speed_mbps = int(speed_match.group(1)) if speed_match else None
            
            iface = InterfaceInfo(
                id=f"iface_{name}",
                name=name,
                ip_address=ip_address,
                status=status,
                mtu=mtu,
                mac_address=mac_address,
                description=description,
                speed_mbps=speed_mbps,
                raw_block=raw_output,
            )
            interfaces.append(iface)
            
            logger.info(f"成功解析接口: {name}")
            
        except Exception as e:
            logger.error(f"解析接口信息失败: {e}", exc_info=True)
        
        return interfaces
    
    def parse_routes(self, raw_output: str) -> List[RouteEntry]:
        """解析路由表
        
        解析 show ip route 命令输出，提取路由条目。
        
        Args:
            raw_output: show ip route 命令输出
            
        Returns:
            RouteEntry 对象列表
        """
        routes = []
        
        if not raw_output:
            logger.warning("路由表输出为空")
            return routes
        
        # RAISECOM 路由表格式示例：
        # S>* 0.0.0.0/0 [10/0] via 211.145.41.254, ge1 weight: 1
        # C>* 5.96.0.188/30 is directly connected, vxlan2500110 weight: 0
        # K>* 5.96.0.189/32 is directly connected, vxlan2500110 weight: 0
        
        for line in raw_output.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('Codes:') or line.startswith('VRF'):
                continue
            
            try:
                route = self._parse_single_route_line(line)
                if route:
                    routes.append(route)
            except Exception as e:
                logger.warning(f"解析路由行失败: {line[:50]}... Error: {e}")
                continue
        
        logger.info(f"成功解析 {len(routes)} 条路由")
        return routes
    
    def _parse_single_route_line(self, line: str) -> Optional[RouteEntry]:
        """解析单条路由行
        
        Args:
            line: 路由表中的一行
            
        Returns:
            RouteEntry 对象，解析失败返回 None
        """
        # 匹配格式：S>* 0.0.0.0/0 [10/0] via 211.145.41.254, ge1 weight: 1
        # 或：C>* 5.96.0.188/30 is directly connected, vxlan2500110 weight: 0
        
        # 提取协议代码
        protocol_match = re.match(r"^([A-Z*>\s]+?)\s+", line)
        if not protocol_match:
            return None
        
        protocol_code = protocol_match.group(1).strip()
        protocol = self._decode_protocol(protocol_code)
        
        # 提取目标网络
        dest_match = re.search(r"\s(\d+\.\d+\.\d+\.\d+/\d+)\s", line)
        if not dest_match:
            return None
        destination = dest_match.group(1)
        
        # 提取网关和接口
        gateway = None
        interface = None
        
        if "via" in line:
            # 有下一跳的路由
            via_match = re.search(r"via\s+(\d+\.\d+\.\d+\.\d+),?\s*(\S+)?", line)
            if via_match:
                gateway = via_match.group(1)
                interface = via_match.group(2) if via_match.group(2) else None
        elif "directly connected" in line:
            # 直连路由
            conn_match = re.search(r"directly connected,\s*(\S+)", line)
            if conn_match:
                interface = conn_match.group(1)
        
        # 提取 metric（weight）
        metric = 0
        weight_match = re.search(r"weight:\s*(\d+)", line)
        if weight_match:
            metric = int(weight_match.group(1))
        
        return RouteEntry(
            id=f"route_{destination.replace('/', '_')}",
            destination=destination,
            gateway=gateway,
            interface=interface,
            metric=metric,
            protocol=protocol,
            raw_line=line,
        )
    
    def _decode_protocol(self, code: str) -> str:
        """解码路由协议代码
        
        Args:
            code: 路由协议代码（如 S, C, K 等）
            
        Returns:
            协议名称字符串
        """
        mapping = {
            "C": "connected",
            "S": "static",
            "K": "kernel",
            "R": "rip",
            "O": "ospf",
            "B": "bgp",
            "D": "dhcp",
            "P": "pppoe",
        }
        # 移除特殊符号（*>等）
        clean_code = code.replace('*', '').replace('>', '').strip()
        return mapping.get(clean_code, f"unknown({clean_code})")
    
    def parse_sdwan_policies(self, raw_output: str) -> List[SdwanPolicy]:
        """解析 SD-WAN 策略
        
        从 running-config 中解析 url-group 配置，提取业务分流策略。
        
        Args:
            raw_output: show running-config 命令输出
            
        Returns:
            SdwanPolicy 对象列表
        """
        policies = []
        
        if not raw_output:
            logger.warning("SD-WAN 策略输出为空")
            return policies
        
        # 使用详细解析结果
        if self.url_groups_detail:
            for url_group in self.url_groups_detail:
                policy = SdwanPolicy(
                    id=f"policy_{url_group.group_name}",
                    name=url_group.group_name,
                    source=url_group.source_ip or "any",
                    destination=",".join(url_group.domains) if url_group.domains else "any",
                    application="dns-based",
                    sla_class=None,
                    preferred_path=url_group.nexthop_master,
                    backup_path=None,
                    raw_block=url_group.raw_block,
                )
                policies.append(policy)
        else:
            # 降级：直接解析
            url_group_pattern = r"url-group\s+(\S+)\s*\n(.*?)^exit"
            matches = re.finditer(url_group_pattern, raw_output, re.MULTILINE | re.DOTALL)
            
            for match in matches:
                group_name = match.group(1)
                block = match.group(2)
                
                try:
                    # 提取 DNS 服务器
                    dns_match = re.search(r"dns server\s+(\S+)", block)
                    dns_server = dns_match.group(1) if dns_match else None
                    
                    # 提取下一跳
                    nexthop_match = re.search(r"nexthop master\s+(\S+)", block)
                    nexthop = nexthop_match.group(1) if nexthop_match else None
                    
                    # 提取域名列表
                    domains = re.findall(r"domain name\s+(\S+)", block)
                    
                    policy = SdwanPolicy(
                        id=f"policy_{group_name}",
                        name=group_name,
                        source="any",
                        destination=",".join(domains) if domains else "any",
                        application="dns-based",
                        sla_class=None,
                        preferred_path=nexthop,
                        backup_path=None,
                        raw_block=block,
                    )
                    policies.append(policy)
                    
                except Exception as e:
                    logger.warning(f"解析 URL 组 '{group_name}' 失败: {e}")
                    continue
        
        logger.info(f"成功解析 {len(policies)} 条 SD-WAN 策略")
        return policies
    
    def parse_vpn_tunnels(self, raw_output: str) -> List[VpnTunnelInfo]:
        """解析 VPN 隧道信息
        
        从 running-config 和 show link detect 输出中解析 VXLAN/L2TP 隧道状态。
        
        Args:
            raw_output: show link detect 或 show running-config 命令输出
            
        Returns:
            VpnTunnelInfo 对象列表
        """
        tunnels = []
        
        if not raw_output:
            logger.warning("VPN 隧道输出为空")
            return tunnels
        
        # 优先解析 show link detect 输出（包含实时状态）
        # 格式示例：
        # vrf default modulename none groupid 1 master vxlan2500110 dest 5.96.0.190 backup vxlan2500110 3 3 scene_2 up none
        
        link_detect_pattern = r"master\s+(\S+)\s+dest\s+(\d+\.\d+\.\d+\.\d+).*?\b(up|down)\b"
        matches = re.finditer(link_detect_pattern, raw_output, re.IGNORECASE)
        
        for match in matches:
            interface = match.group(1)
            remote_ip = match.group(2)
            state = match.group(3).lower()
            
            tunnel = VpnTunnelInfo(
                id=f"tunnel_{interface}",
                remote_ip=remote_ip,
                local_color=interface,
                remote_color="",
                state=state,
                type="vxlan",
                uptime_seconds=None,
            )
            tunnels.append(tunnel)
        
        # 如果没有找到 link detect 输出，尝试从 running-config 解析隧道定义
        if not tunnels:
            tunnel_pattern = r"tunnel\s+(tunnel\d+)\s*\n.*?type\s+(\S+).*?peer\s+(\d+\.\d+\.\d+\.\d+)"
            matches = re.finditer(tunnel_pattern, raw_output, re.MULTILINE | re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                tunnel_name = match.group(1)
                tunnel_type = match.group(2).lower()
                peer_ip = match.group(3)
                
                tunnel = VpnTunnelInfo(
                    id=f"tunnel_{tunnel_name}",
                    remote_ip=peer_ip,
                    local_color=tunnel_name,
                    remote_color="",
                    state="unknown",
                    type=tunnel_type,
                    uptime_seconds=None,
                )
                tunnels.append(tunnel)
        
        logger.info(f"成功解析 {len(tunnels)} 条 VPN 隧道")
        return tunnels
    
    def parse_nat_rules(self, raw_output: str) -> List[NatRuleInfo]:
        """解析 NAT 规则
        
        从 running-config 中解析 ip nat source 配置。
        
        Args:
            raw_output: show running-config 命令输出
            
        Returns:
            NatRuleInfo 对象列表
        """
        nat_rules = []
        
        if not raw_output:
            logger.warning("NAT 规则输出为空")
            return nat_rules
        
        # 解析 ip nat source 配置
        # 格式示例：
        # ip nat source cell any any any interface 110
        # ip nat source ge1 any any any interface 1
        
        nat_pattern = r"ip nat source\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+interface\s+(\d+)"
        matches = re.finditer(nat_pattern, raw_output, re.MULTILINE | re.IGNORECASE)
        
        for match in matches:
            source_interface = match.group(1)
            src_addr = match.group(2)
            dst_addr = match.group(3)
            proto = match.group(4)
            out_interface = match.group(5)
            
            nat_rule = NatRuleInfo(
                id=f"nat_{source_interface}_to_{out_interface}",
                protocol=proto,
                inside_addr=f"{src_addr} ({source_interface})",
                outside_addr=f"interface {out_interface}",
                nat_type="dynamic",
                raw_line=match.group(0),
            )
            nat_rules.append(nat_rule)
        
        logger.info(f"成功解析 {len(nat_rules)} 条 NAT 规则")
        return nat_rules
    
    def parse_all(self, raw_outputs: Dict[str, str]) -> CpeConfiguration:
        """解析所有命令输出，构建完整的CPE配置对象
        
        Args:
            raw_outputs: 命令名称到输出的映射字典
                例如: {"show version all": "...", "show running-config": "..."}
                
        Returns:
            完整的 CpeConfiguration 对象
        """
        # 获取各命令输出
        version_output = raw_outputs.get("show version all", "")
        config_output = raw_outputs.get("show running-config", "")
        route_output = raw_outputs.get("show ip route", "")
        link_detect_output = raw_outputs.get("show link detect", "")
        cpu_output = raw_outputs.get("show cpu usage", "")
        mem_output = raw_outputs.get("show memory usage", "")
        uptime_output = raw_outputs.get("show system uptime", "")
        dns_output = raw_outputs.get("show dns active", "")
        arp_output = raw_outputs.get("show arp", "")
        callhome_output = raw_outputs.get("show callhome all", "")
        security_ip_output = raw_outputs.get("show url-group all security-ip", "")
        ip_rule_output = raw_outputs.get("diagnose:ip rule show", "")
        policy_route_99 = raw_outputs.get("diagnose:ip route show table 99", "")
        policy_route_100 = raw_outputs.get("diagnose:ip route show table 100", "")
        
        # 解析基础信息
        vendor = self.get_vendor_name()
        model = self._detect_model(version_output)
        version = self.parse_version(version_output)
        hostname = self._detect_hostname(config_output or version_output)
        
        # 解析系统详细信息
        self.parse_system_info(version_output)
        self.parse_cpu_memory_info(cpu_output, mem_output, uptime_output)
        
        # 解析用户和视图
        self.parse_users(config_output)
        # 视图需要从完整交互日志中解析，这里简化处理
        self.parse_views(version_output + config_output)
        
        # 解析 DNS、ARP、Callhome
        self.parse_dns_configs(dns_output)
        self.parse_arp_table(arp_output)
        self.parse_callhome(callhome_output)
        
        # 解析 L2TP 和 URL 组
        self.parse_l2tp_groups(config_output)
        self.parse_url_groups_detail(config_output, security_ip_output)
        
        # 解析策略路由
        self.parse_ip_rules(ip_rule_output)
        self.parse_policy_routes(policy_route_99, "99")
        self.parse_policy_routes(policy_route_100, "100")
        
        # 解析接口（需要从多个 show interface 命令输出中聚合）
        interfaces = []
        for cmd_name, output in raw_outputs.items():
            if cmd_name.startswith("show interface "):
                iface_list = self.parse_interfaces(output)
                interfaces.extend(iface_list)
        
        # 解析其他配置
        routes = self.parse_routes(route_output) if route_output else []
        sdwan_policies = self.parse_sdwan_policies(config_output) if config_output else []
        vpn_tunnels = self.parse_vpn_tunnels(link_detect_output or config_output) if (link_detect_output or config_output) else []
        nat_rules = self.parse_nat_rules(config_output) if config_output else []
        
        # 构建配置对象
        config = CpeConfiguration(
            id=f"cpe_{hostname}_{model}",
            vendor=vendor,
            model=model,
            version=version,
            hostname=hostname,
            interfaces=interfaces,
            routes=routes,
            sdwan_policies=sdwan_policies,
            vpn_tunnels=vpn_tunnels,
            nat_rules=nat_rules,
            raw_outputs=raw_outputs,
        )
        
        logger.info(
            f"RAISECOM MSG5200A 配置解析完成: "
            f"hostname={hostname}, model={model}, version={version}, "
            f"interfaces={len(interfaces)}, routes={len(routes)}, "
            f"policies={len(sdwan_policies)}, tunnels={len(vpn_tunnels)}, "
            f"nat_rules={len(nat_rules)}, users={len(self.users)}, "
            f"url_groups={len(self.url_groups_detail)}"
        )
        
        return config