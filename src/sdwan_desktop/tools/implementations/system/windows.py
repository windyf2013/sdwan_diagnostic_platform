"""
Windows系统信息采集工具

遵循 SDWAN_SPEC.md §2.4.1 工具约束
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
遵循 detail_function_design.md §1.1 信息采集清单
"""

import asyncio
import logging
import re
import subprocess
import sys
import winreg
from typing import Any, Dict, List, Optional, Tuple

from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.system import (
    AdapterInfo, AdapterStatus, AdapterType, RouteInfo,
    DnsConfigInfo, ProxyConfigInfo, FirewallInfo, ArpEntry, ConnectionInfo,
    Ipv6Info, SystemInfoSnapshot
)
from sdwan_desktop.tools.registry.decorator import tool_function

logger = logging.getLogger(__name__)


@tool_function(
    name="windows_system",
    description="Windows系统信息采集工具，采集网卡、路由、DNS、代理、防火墙等配置",
    timeout=60,
    retry_count=0,
    input_schema={
        "type": "object",
        "properties": {
            "collect_adapters": {"type": "boolean", "default": True},
            "collect_routes": {"type": "boolean", "default": True},
            "collect_dns": {"type": "boolean", "default": True},
            "collect_proxy": {"type": "boolean", "default": True},
            "collect_firewall": {"type": "boolean", "default": True},
            "collect_arp": {"type": "boolean", "default": True},
            "collect_connections": {"type": "boolean", "default": False},
            "collect_ipv6": {"type": "boolean", "default": True},
        },
        "required": [],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "snapshot": {
                "type": "object",
                "description": "系统信息快照",
                "properties": {
                    "adapters": {"type": "array", "items": {"type": "object"}},
                    "routes": {"type": "array", "items": {"type": "object"}},
                    "dns_config": {"type": "object"},
                    "proxy_config": {"type": "object"},
                    "firewall_status": {"type": "object"},
                    "arp_table": {"type": "array", "items": {"type": "object"}},
                    "active_connections": {"type": "array", "items": {"type": "object"}},
                    "ipv6": {"type": "object"},
                    "hostname": {"type": "string"},
                    "os_version": {"type": "string"},
                    "architecture": {"type": "string"},
                    "uptime_seconds": {"type": "integer"},
                },
            },
            "error_message": {"type": "string"},
        },
        "required": ["success"],
    },
)
class WindowsSystemTool:
    """Windows系统信息采集工具
    
    采集Windows系统的网络配置信息，包括：
    1. 网卡配置
    2. 路由表
    3. DNS配置
    4. 代理设置
    5. 防火墙状态
    6. ARP表
    7. 活动连接
    8. IPv6配置
    """
    
    def __init__(self):
        """初始化Windows系统工具"""
        self._wmi_client = None
    
    async def execute(self, request: ToolRequest, ctx: FlowContext) -> ToolResponse:
        """执行系统信息采集
        
        Args:
            request: 工具请求，parameters包含采集选项
            ctx: 流程上下文
            
        Returns:
            ToolResponse: 采集结果
        """
        # 1. 参数解析
        params = request.parameters
        collect_options = {
            "adapters": params.get("collect_adapters", True),
            "routes": params.get("collect_routes", True),
            "dns": params.get("collect_dns", True),
            "proxy": params.get("collect_proxy", True),
            "firewall": params.get("collect_firewall", True),
            "arp": params.get("collect_arp", True),
            "connections": params.get("collect_connections", False),
            "ipv6": params.get("collect_ipv6", True),
        }
        
        try:
            logger.info(
                f"开始采集Windows系统信息: {collect_options}",
                extra={"trace_id": ctx.trace_id}
            )
            
            start_time = asyncio.get_event_loop().time()
            
            # 2. 使用同步方法采集（简化实现）
            snapshot = await self._collect_all_sync(collect_options, ctx)
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            logger.info(
                f"Windows系统信息采集完成: "
                f"网卡={len(snapshot.adapters)}, "
                f"路由={len(snapshot.routes)}, "
                f"ARP={len(snapshot.arp_table)}",
                extra={"trace_id": ctx.trace_id}
            )
            
            return ToolResponse(
                success=True,
                data={
                    "snapshot": snapshot.to_dict(),
                },
                trace_id=ctx.trace_id,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            logger.error(
                f"Windows系统信息采集失败: {e}",
                extra={"trace_id": ctx.trace_id}
            )
            return ToolResponse(
                success=False,
                error_code="TOOL_002",
                error_message=str(e),
                trace_id=ctx.trace_id
            )
    
    async def _collect_all_sync(
        self, 
        collect_options: Dict[str, bool], 
        ctx: FlowContext
    ) -> SystemInfoSnapshot:
        """同步采集所有信息"""
        snapshot = SystemInfoSnapshot()
        
        # 采集网卡信息
        if collect_options["adapters"]:
            try:
                snapshot.adapters = await self._get_network_adapters(ctx)
            except Exception as e:
                logger.warning(f"采集网卡信息失败: {e}", extra={"trace_id": ctx.trace_id})
        
        # 采集路由表
        if collect_options["routes"]:
            try:
                snapshot.routes = await self._get_routing_table(ctx)
            except Exception as e:
                logger.warning(f"采集路由表失败: {e}", extra={"trace_id": ctx.trace_id})
        
        # 采集DNS配置
        if collect_options["dns"]:
            try:
                snapshot.dns_config = await self._get_dns_config(ctx)
            except Exception as e:
                logger.warning(f"采集DNS配置失败: {e}", extra={"trace_id": ctx.trace_id})
        
        # 采集代理配置
        if collect_options["proxy"]:
            try:
                snapshot.proxy_config = await self._get_proxy_config(ctx)
            except Exception as e:
                logger.warning(f"采集代理配置失败: {e}", extra={"trace_id": ctx.trace_id})
        
        # 采集防火墙状态
        if collect_options["firewall"]:
            try:
                snapshot.firewall_status = await self._get_firewall_status(ctx)
            except Exception as e:
                logger.warning(f"采集防火墙状态失败: {e}", extra={"trace_id": ctx.trace_id})
        
        # 采集ARP表
        if collect_options["arp"]:
            try:
                snapshot.arp_table = await self._get_arp_table(ctx)
            except Exception as e:
                logger.warning(f"采集ARP表失败: {e}", extra={"trace_id": ctx.trace_id})
        
        # 采集活动连接
        if collect_options["connections"]:
            try:
                snapshot.active_connections = await self._get_active_connections(ctx)
            except Exception as e:
                logger.warning(f"采集活动连接失败: {e}", extra={"trace_id": ctx.trace_id})
        
        # 采集IPv6信息
        if collect_options["ipv6"]:
            try:
                snapshot.ipv6 = await self._get_ipv6_info(ctx)
            except Exception as e:
                logger.warning(f"采集IPv6信息失败: {e}", extra={"trace_id": ctx.trace_id})
        
        # 采集系统信息
        try:
            system_info = await self._get_system_info(ctx)
            snapshot.hostname = system_info.get("hostname")
            snapshot.os_version = system_info.get("os_version")
            snapshot.architecture = system_info.get("architecture")
            snapshot.uptime_seconds = system_info.get("uptime_seconds")
        except Exception as e:
            logger.warning(f"采集系统信息失败: {e}", extra={"trace_id": ctx.trace_id})
        
        return snapshot
    
    async def _get_network_adapters(self, ctx: FlowContext) -> List[AdapterInfo]:
        """获取网卡配置信息"""
        adapters = []
        
        try:
            # 尝试使用WMI
            import wmi
            wmi_client = wmi.WMI()
            
            for nic in wmi_client.Win32_NetworkAdapterConfiguration(IPEnabled=True):
                adapter = AdapterInfo(
                    name=nic.Description or "Unknown",
                    description=nic.Description or "Unknown",
                    mac_address=nic.MACAddress or "00:00:00:00:00:00",
                    adapter_type=self._detect_adapter_type(nic.Description or ""),
                    status=AdapterStatus.CONNECTED if nic.IPEnabled else AdapterStatus.DISCONNECTED,
                    is_connected=nic.IPEnabled,
                    speed_mbps=self._get_adapter_speed(nic),
                    ip_addresses=list(nic.IPAddress) if nic.IPAddress else [],
                    ip_subnets=list(nic.IPSubnet) if nic.IPSubnet else [],
                    default_gateway=nic.DefaultIPGateway[0] if nic.DefaultIPGateway else None,
                    dhcp_enabled=nic.DHCPEnabled,
                    dns_servers=list(nic.DNSServerSearchOrder) if nic.DNSServerSearchOrder else [],
                    dns_suffix=nic.DNSDomainSuffixSearchOrder[0] if nic.DNSDomainSuffixSearchOrder else None,
                    mtu=nic.MTU or 1500,
                    physical_address=nic.PhysicalAddress,
                    manufacturer=nic.Manufacturer,
                    driver_version=nic.DriverVersion,
                )
                adapters.append(adapter)
                
        except ImportError:
            # WMI不可用，使用ipconfig命令
            logger.warning("WMI不可用，使用ipconfig命令采集网卡信息", extra={"trace_id": ctx.trace_id})
            adapters = await self._get_adapters_from_ipconfig(ctx)
        
        except Exception as e:
            logger.error(f"WMI采集网卡信息失败: {e}", extra={"trace_id": ctx.trace_id})
            # 回退到ipconfig命令
            adapters = await self._get_adapters_from_ipconfig(ctx)
        
        return adapters
    
    async def _get_adapters_from_ipconfig(self, ctx: FlowContext) -> List[AdapterInfo]:
        """从ipconfig命令获取网卡信息"""
        adapters = []
        
        try:
            # 执行ipconfig /all命令
            result = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                encoding="gbk",  # Windows中文系统使用gbk编码
                errors="ignore"
            )
            
            if result.returncode != 0:
                logger.error(f"ipconfig命令执行失败: {result.stderr}", extra={"trace_id": ctx.trace_id})
                return adapters
            
            output = result.stdout
            
            # 解析ipconfig输出
            # 这里需要实现复杂的解析逻辑
            # 简化实现：返回空列表
            logger.warning("ipconfig解析未实现，返回空网卡列表", extra={"trace_id": ctx.trace_id})
            
        except Exception as e:
            logger.error(f"ipconfig命令执行异常: {e}", extra={"trace_id": ctx.trace_id})
        
        return adapters
    
    def _detect_adapter_type(self, description: str) -> AdapterType:
        """检测网卡类型"""
        description_lower = description.lower()
        
        if "wireless" in description_lower or "wifi" in description_lower or "802.11" in description_lower:
            return AdapterType.WIFI
        elif "loopback" in description_lower:
            return AdapterType.LOOPBACK
        elif "tunnel" in description_lower or "vpn" in description_lower:
            return AdapterType.TUNNEL
        elif "virtual" in description_lower or "vmware" in description_lower or "virtualbox" in description_lower:
            return AdapterType.VIRTUAL
        else:
            return AdapterType.ETHERNET
    
    def _get_adapter_speed(self, nic) -> Optional[int]:
        """获取网卡速度"""
        try:
            # 尝试从WMI获取速度
            if hasattr(nic, 'Speed'):
                speed = nic.Speed
                if speed and speed > 0:
                    return speed // 1000000  # 转换为Mbps
        except:
            pass
        return None
    
    async def _get_routing_table(self, ctx: FlowContext) -> List[RouteInfo]:
        """获取路由表"""
        routes = []
        
        try:
            # 执行route print命令
            result = subprocess.run(
                ["route", "print", "-4"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="ignore"
            )
            
            if result.returncode != 0:
                logger.error(f"route命令执行失败: {result.stderr}", extra={"trace_id": ctx.trace_id})
                return routes
            
            output = result.stdout
            
            # 解析路由表输出
            lines = output.split('\n')
            in_routes = False
            
            for line in lines:
                line = line.strip()
                
                # 跳过空行和表头
                if not line:
                    continue
                
                # 检测路由表开始
                if "网络目标" in line and "网络掩码" in line and "网关" in line:
                    in_routes = True
                    continue
                elif "Network Destination" in line and "Netmask" in line and "Gateway" in line:
                    in_routes = True
                    continue
                
                if in_routes:
                    # 解析路由行
                    # 格式: 网络目标 网络掩码 网关 接口 跃点数
                    # 或者: Network Destination Netmask Gateway Interface Metric
                    parts = re.split(r'\s+', line)
                    if len(parts) >= 5:
                        try:
                            destination = parts[0]
                            netmask = parts[1]
                            gateway = parts[2]
                            interface = parts[3]
                            metric = int(parts[4])
                            
                            # 判断协议类型
                            protocol = "static"
                            if gateway == "0.0.0.0" and destination == "0.0.0.0":
                                protocol = "local"
                            elif gateway == "0.0.0.0":
                                protocol = "connected"
                            
                            route = RouteInfo(
                                destination=destination,
                                netmask=netmask,
                                gateway=gateway,
                                interface=interface,
                                metric=metric,
                                protocol=protocol,
                                persistent=False  # 需要从其他输出判断
                            )
                            routes.append(route)
                        except (ValueError, IndexError):
                            # 跳过解析失败的行
                            continue
                    
                    # 检测路由表结束
                    if "=" in line or "==" in line:
                        break
        
        except Exception as e:
            logger.error(f"解析路由表失败: {e}", extra={"trace_id": ctx.trace_id})
        
        return routes
    
    async def _get_dns_config(self, ctx: FlowContext) -> DnsConfigInfo:
        """获取DNS配置"""
        try:
            # 执行ipconfig /all命令获取DNS信息
            result = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="ignore"
            )
            
            if result.returncode != 0:
                logger.error(f"ipconfig命令执行失败: {result.stderr}", extra={"trace_id": ctx.trace_id})
                return DnsConfigInfo(servers=[])
            
            output = result.stdout
            
            # 解析DNS服务器
            dns_servers = []
            
            # 查找DNS服务器行
            # 中文系统: "DNS 服务器"
            # 英文系统: "DNS Servers"
            for line in output.split('\n'):
                line = line.strip()
                if "DNS 服务器" in line or "DNS Servers" in line:
                    # 提取IP地址
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    if match:
                        dns_servers.append(match.group(1))
            
            return DnsConfigInfo(
                servers=dns_servers,
                suffix_search_order=[],
                primary_dns_suffix=None,
                connection_specific_suffix=None,
                registration_enabled=True,
                dynamic_update_enabled=True
            )
            
        except Exception as e:
            logger.error(f"获取DNS配置失败: {e}", extra={"trace_id": ctx.trace_id})
            return DnsConfigInfo(servers=[])
    
    async def _get_proxy_config(self, ctx: FlowContext) -> ProxyConfigInfo:
        """获取代理配置"""
        try:
            # 从注册表读取代理配置
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                # 读取代理启用状态
                try:
                    proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
                    proxy_enable = bool(proxy_enable)
                except FileNotFoundError:
                    proxy_enable = False
                
                # 读取代理服务器地址
                try:
                    proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
                except FileNotFoundError:
                    proxy_server = ""
                
                # 读取代理例外列表
                try:
                    proxy_override = winreg.QueryValueEx(key, "ProxyOverride")[0]
                except FileNotFoundError:
                    proxy_override = ""
                
                return ProxyConfigInfo(
                    enabled=proxy_enable,
                    server=proxy_server,
                    bypass_list=proxy_override.split(";") if proxy_override else [],
                    auto_detect=False,  # 需要从其他注册表项读取
                    auto_config_url=""
                )
                
        except Exception as e:
            logger.error(f"获取代理配置失败: {e}", extra={"trace_id": ctx.trace_id})
            return ProxyConfigInfo(enabled=False, server="", bypass_list=[])
    
    async def _get_firewall_status(self, ctx: FlowContext) -> FirewallInfo:
        """获取防火墙状态"""
        try:
            # 执行netsh命令获取防火墙状态
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="ignore"
            )
            
            if result.returncode != 0:
                logger.error(f"netsh命令执行失败: {result.stderr}", extra={"trace_id": ctx.trace_id})
                return FirewallInfo(enabled=False, profiles={})
            
            output = result.stdout
            
            # 解析防火墙状态
            profiles = {}
            current_profile = None
            
            for line in output.split('\n'):
                line = line.strip()
                
                # 检测配置文件
                if "域配置文件" in line or "Domain Profile" in line:
                    current_profile = "domain"
                elif "专用配置文件" in line or "Private Profile" in line:
                    current_profile = "private"
                elif "公用配置文件" in line or "Public Profile" in line:
                    current_profile = "public"
                
                # 检测状态
                if current_profile and ("状态" in line or "State" in line):
                    if "启用" in line or "ON" in line:
                        profiles[current_profile] = True
                    elif "关闭" in line or "OFF" in line:
                        profiles[current_profile] = False
            
            # 判断是否启用
            enabled = any(profiles.values())
            
            return FirewallInfo(
                enabled=enabled,
                profiles=profiles,
                icmp_blocked=False,  # 需要从其他规则判断
                inbound_default_action="block" if enabled else "allow",
                outbound_default_action="allow"
            )
            
        except Exception as e:
            logger.error(f"获取防火墙状态失败: {e}", extra={"trace_id": ctx.trace_id})
            return FirewallInfo(enabled=False, profiles={})
    
    async def _get_arp_table(self, ctx: FlowContext) -> List[ArpEntry]:
        """获取ARP表"""
        arp_entries = []
        
        try:
            # 执行arp -a命令
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="ignore"
            )
            
            if result.returncode != 0:
                logger.error(f"arp命令执行失败: {result.stderr}", extra={"trace_id": ctx.trace_id})
                return arp_entries
            
            output = result.stdout
            
            # 解析ARP表
            for line in output.split('\n'):
                line = line.strip()
                
                # 跳过空行和表头
                if not line or "接口" in line or "Interface" in line:
                    continue
                
                # 解析ARP条目
                # 格式: IP地址 物理地址 类型
                parts = re.split(r'\s+', line)
                if len(parts) >= 3:
                    try:
                        ip_address = parts[0]
                        mac_address = parts[1]
                        entry_type = parts[2].lower()
                        
                        # 判断类型
                        is_dynamic = entry_type == "dynamic"
                        is_static = entry_type == "static"
                        
                        arp_entry = ArpEntry(
                            ip_address=ip_address,
                            mac_address=mac_address,
                            interface="",  # 需要从上下文获取
                            is_dynamic=is_dynamic,
                            is_static=is_static,
                            age_seconds=None  # Windows arp不显示年龄
                        )
                        arp_entries.append(arp_entry)
                    except (ValueError, IndexError):
                        # 跳过解析失败的行
                        continue
        
        except Exception as e:
            logger.error(f"获取ARP表失败: {e}", extra={"trace_id": ctx.trace_id})
        
        return arp_entries
    
    async def _get_active_connections(self, ctx: FlowContext) -> List[ConnectionInfo]:
        """获取活动连接"""
        connections = []
        
        try:
            # 执行netstat -an命令
            result = subprocess.run(
                ["netstat", "-an"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="ignore"
            )
            
            if result.returncode != 0:
                logger.error(f"netstat命令执行失败: {result.stderr}", extra={"trace_id": ctx.trace_id})
                return connections
            
            output = result.stdout
            
            # 解析netstat输出
            for line in output.split('\n'):
                line = line.strip()
                
                # 跳过空行和表头
                if not line or "活动连接" in line or "Active Connections" in line:
                    continue
                
                # 解析连接行
                # 格式: 协议 本地地址 外部地址 状态
                parts = re.split(r'\s+', line)
                if len(parts) >= 4:
                    try:
                        protocol = parts[0].lower()
                        local_address = parts[1]
                        foreign_address = parts[2]
                        state = parts[3].lower()
                        
                        # 解析本地地址和端口
                        local_parts = local_address.split(':')
                        local_ip = local_parts[0] if len(local_parts) > 0 else ""
                        local_port = int(local_parts[1]) if len(local_parts) > 1 else 0
                        
                        # 解析外部地址和端口
                        foreign_parts = foreign_address.split(':')
                        foreign_ip = foreign_parts[0] if len(foreign_parts) > 0 else ""
                        foreign_port = int(foreign_parts[1]) if len(foreign_parts) > 1 else 0
                        
                        # 判断连接状态
                        is_listening = state == "listening"
                        is_established = state == "established"
                        is_time_wait = state == "time_wait"
                        is_close_wait = state == "close_wait"
                        
                        connection = ConnectionInfo(
                            protocol=protocol,
                            local_ip=local_ip,
                            local_port=local_port,
                            foreign_ip=foreign_ip,
                            foreign_port=foreign_port,
                            state=state,
                            is_listening=is_listening,
                            is_established=is_established,
                            pid=None,  # netstat -an不显示PID
                            process_name=None
                        )
                        connections.append(connection)
                    except (ValueError, IndexError):
                        # 跳过解析失败的行
                        continue
        
        except Exception as e:
            logger.error(f"获取活动连接失败: {e}", extra={"trace_id": ctx.trace_id})
        
        return connections
    
    async def _get_ipv6_info(self, ctx: FlowContext) -> Ipv6Info:
        """获取IPv6信息"""
        try:
            # 执行ipconfig命令获取IPv6信息
            result = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="ignore"
            )
            
            if result.returncode != 0:
                logger.error(f"ipconfig命令执行失败: {result.stderr}", extra={"trace_id": ctx.trace_id})
                return Ipv6Info(enabled=False, addresses=[], is_preferred=False)
            
            output = result.stdout
            
            # 检查是否有IPv6地址
            has_ipv6 = False
            ipv6_addresses = []
            
            for line in output.split('\n'):
                line = line.strip()
                # 查找IPv6地址
                if "IPv6 地址" in line or "IPv6 Address" in line:
                    has_ipv6 = True
                    # 提取IPv6地址
                    match = re.search(r'([0-9a-fA-F:]+(?:%[0-9a-zA-Z]+)?)', line)
                    if match:
                        ipv6_addresses.append(match.group(1))
            
            return Ipv6Info(
                enabled=has_ipv6,
                addresses=ipv6_addresses,
                is_preferred=False,  # 需要从路由表判断
                dns_servers=[],
                gateway=None
            )
            
        except Exception as e:
            logger.error(f"获取IPv6信息失败: {e}", extra={"trace_id": ctx.trace_id})
            return Ipv6Info(enabled=False, addresses=[], is_preferred=False)
    
    async def _get_system_info(self, ctx: FlowContext) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            import platform
            import socket
            
            # 获取主机名
            hostname = socket.gethostname()
            
            # 获取操作系统信息
            os_info = platform.uname()
            os_version = f"{os_info.system} {os_info.release} {os_info.version}"
            architecture = os_info.machine
            
            # 获取系统启动时间（简化实现）
            uptime_seconds = 0
            
            return {
                "hostname": hostname,
                "os_version": os_version,
                "architecture": architecture,
                "uptime_seconds": uptime_seconds
            }
            
        except Exception as e:
            logger.error(f"获取系统信息失败: {e}", extra={"trace_id": ctx.trace_id})
            return {
                "hostname": "unknown",
                "os_version": "unknown",
                "architecture": "unknown",
                "uptime_seconds": 0
            }
