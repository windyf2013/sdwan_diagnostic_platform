"""
Windows系统信息采集工具

遵循 SDWAN_SPEC.md §2.4.1 工具约束
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
遵循 detail_function_design.md §1.1 信息采集清单
"""

import asyncio
import logging
import re
from sdwan_desktop.core.subprocess_platform import run_hidden
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
                logger.debug(f"[Tool] 采集到 {len(snapshot.adapters)} 个网卡", extra={"trace_id": ctx.trace_id})
                for i, adapter in enumerate(snapshot.adapters):
                    logger.debug(f"[Tool] 网卡 {i}: name={adapter.name}, is_connected={adapter.is_connected}, ip={adapter.ip_addresses}, gw={adapter.default_gateway}", extra={"trace_id": ctx.trace_id})
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
                try:
                    # 安全获取各个属性，处理可能的 COMError 或 AttributeError
                    def safe_get(obj, attr, default=None):
                        try:
                            return getattr(obj, attr, default)
                        except Exception:
                            return default

                    adapter = AdapterInfo(
                        name=safe_get(nic, "Description", "Unknown"),
                        description=safe_get(nic, "Description", "Unknown"),
                        mac_address=safe_get(nic, "MACAddress", "00:00:00:00:00:00"),
                        adapter_type=self._detect_adapter_type(safe_get(nic, "Description", "")),
                        status=AdapterStatus.CONNECTED if safe_get(nic, "IPEnabled") else AdapterStatus.DISCONNECTED,
                        is_connected=safe_get(nic, "IPEnabled"),
                        speed_mbps=self._get_adapter_speed(nic),
                        ip_addresses=list(safe_get(nic, "IPAddress")) if safe_get(nic, "IPAddress") else [],
                        ip_subnets=list(safe_get(nic, "IPSubnet")) if safe_get(nic, "IPSubnet") else [],
                        default_gateway=safe_get(nic, "DefaultIPGateway")[0] if safe_get(nic, "DefaultIPGateway") else None,
                        dhcp_enabled=safe_get(nic, "DHCPEnabled"),
                        dns_servers=list(safe_get(nic, "DNSServerSearchOrder")) if safe_get(nic, "DNSServerSearchOrder") else [],
                        dns_suffix=safe_get(nic, "DNSDomainSuffixSearchOrder")[0] if safe_get(nic, "DNSDomainSuffixSearchOrder") else None,
                        mtu=safe_get(nic, "MTU") or 1500,
                        physical_address=safe_get(nic, "PhysicalAddress"),
                        manufacturer=safe_get(nic, "Manufacturer"),
                        driver_version=safe_get(nic, "DriverVersion"),
                    )
                    adapters.append(adapter)
                except Exception as e:
                    logger.warning(f"解析单个网卡配置失败: {e}", extra={"trace_id": ctx.trace_id})
                
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
            result = run_hidden(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                encoding="gbk",  # Windows中文系统使用gbk编码
                errors="ignore",
            )
            
            if result.returncode != 0:
                logger.error(f"ipconfig命令执行失败: {result.stderr}", extra={"trace_id": ctx.trace_id})
                return adapters
            
            output = result.stdout
            
            # 解析ipconfig输出
            current_adapter = None
            for line in output.splitlines():
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                
                # 检测新适配器开始
                is_new_adapter = False
                adapter_name = ""
                
                # 格式1: "以太网适配器 名称:" (中文系统)
                # 格式2: "Ethernet adapter Name:" (英文系统)
                if line_stripped.startswith("以太网适配器") or line_stripped.startswith("无线局域网适配器"):
                    is_new_adapter = True
                    # 提取冒号前的部分，去掉前缀
                    if ":" in line_stripped:
                        adapter_name = line_stripped.split(":")[0].strip()
                        if "适配器" in adapter_name:
                            adapter_name = adapter_name.split("适配器", 1)[1].strip()
                elif line_stripped.lower().startswith("ethernet adapter") or line_stripped.lower().startswith("wireless lan adapter"):
                    is_new_adapter = True
                    if ":" in line_stripped:
                        adapter_name = line_stripped.split(":")[0].strip()
                        # 去掉 "Ethernet adapter" 或 "Wireless LAN adapter" 前缀
                        if "adapter" in adapter_name.lower():
                            adapter_name = adapter_name.split("adapter", 1)[1].strip()
                
                if is_new_adapter:
                    if current_adapter:
                        adapters.append(current_adapter)
                    
                    current_adapter = AdapterInfo(
                        name=adapter_name,
                        description=adapter_name,
                        mac_address="00:00:00:00:00:00",
                        adapter_type=AdapterType.ETHERNET,
                        status=AdapterStatus.DISCONNECTED,
                        is_connected=False,
                        mtu=1500,
                    )
                    logger.debug(f"[IPCONFIG] 识别到新适配器: {adapter_name}", extra={"trace_id": ctx.trace_id})
                    continue  # 跳过后续处理
                
                # 如果当前没有活动的适配器，跳过这一行
                if not current_adapter:
                    continue
                
                # 优先处理媒体状态，因为它决定了网卡是否真的连通
                if "媒体状态" in line or "Media State" in line:
                    if "媒体已断开" in line or "Media disconnected" in line:
                        current_adapter.status = AdapterStatus.DISCONNECTED
                        current_adapter.is_connected = False
                        current_adapter.ip_addresses = []
                        current_adapter.default_gateway = None
                        logger.debug(f"[IPCONFIG] 适配器 {current_adapter.name} 媒体已断开", extra={"trace_id": ctx.trace_id})
                    continue

                if "IPv4 地址" in line or "IPv4 Address" in line:
                    ip_part = line.split(":")[-1].strip()
                    if "(首选)" in ip_part or "(Preferred)" in ip_part:
                        ip_part = ip_part.split("(")[0].strip()
                    if not current_adapter.ip_addresses:
                        current_adapter.ip_addresses = [ip_part]
                    else:
                        current_adapter.ip_addresses.append(ip_part)
                    
                    # 只要有IP，且没有明确的"媒体已断开"标记，则认为是连接的
                    if not ip_part.startswith("169.254"):
                        current_adapter.is_connected = True
                        current_adapter.status = AdapterStatus.CONNECTED
                        logger.debug(f"[IPCONFIG] 适配器 {current_adapter.name} 获取到IP: {ip_part}, 状态更新为连接", extra={"trace_id": ctx.trace_id})
                    continue

                if "子网掩码" in line or "Subnet Mask" in line:
                    mask = line.split(":")[-1].strip()
                    if not current_adapter.ip_subnets:
                        current_adapter.ip_subnets = [mask]
                    else:
                        current_adapter.ip_subnets.append(mask)
                    continue

                if "默认网关" in line or "Default Gateway" in line:
                    gw = line.split(":")[-1].strip()
                    if gw and gw != "0.0.0.0":
                        current_adapter.default_gateway = gw
                    continue

                if "DHCP 已启用" in line or "DHCP Enabled" in line:
                    if "是" in line or "Yes" in line:
                        current_adapter.dhcp_enabled = True
                    else:
                        current_adapter.dhcp_enabled = False
                    continue

                if "DNS 服务器" in line or "DNS Servers" in line:
                    dns = line.split(":")[-1].strip()
                    if dns:
                        if not current_adapter.dns_servers:
                            current_adapter.dns_servers = [dns]
                        else:
                            current_adapter.dns_servers.append(dns)
                    continue

                if "连接特定的 DNS 后缀" in line or "Connection-specific DNS Suffix" in line:
                    suffix = line.split(":")[-1].strip()
                    if suffix:
                        current_adapter.dns_suffix = suffix
                    continue
                
                if "物理地址" in line or "Physical Address" in line:
                    mac = line.split(":")[-1].strip().replace("-", ":")
                    if len(mac) == 17:  # 有效的MAC地址格式
                        current_adapter.mac_address = mac
                    continue

            if current_adapter:
                adapters.append(current_adapter)
            
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
            if hasattr(nic, 'Speed'):
                speed = nic.Speed
                if speed and speed > 0:
                    return speed // 1000000
        except:
            pass
        return None
    
    async def _get_routing_table(self, ctx: FlowContext) -> List[RouteInfo]:
        """获取路由表"""
        routes = []
        try:
            result = run_hidden(
                ["route", "print", "-4"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="ignore",
            )
            if result.returncode != 0:
                return routes
            
            output = result.stdout
            lines = output.split('\n')
            in_routes = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if "网络目标" in line or "Network Destination" in line:
                    in_routes = True
                    continue
                
                if in_routes:
                    parts = re.split(r'\s+', line)
                    if len(parts) >= 5:
                        try:
                            route = RouteInfo(
                                destination=parts[0],
                                netmask=parts[1],
                                gateway=parts[2],
                                interface=parts[3],
                                metric=int(parts[4]) if parts[4].isdigit() else 0,
                            )
                            routes.append(route)
                        except:
                            continue
        except Exception as e:
            logger.error(f"采集路由表失败: {e}", extra={"trace_id": ctx.trace_id})
        return routes

    async def _get_dns_config(self, ctx: FlowContext) -> Optional[DnsConfigInfo]:
        """获取DNS配置"""
        try:
            result = run_hidden(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="ignore",
            )

            if result.returncode != 0:
                return DnsConfigInfo(servers=[])
            
            output = result.stdout
            dns_servers = []
            
            # 简单解析 DNS 服务器
            for line in output.splitlines():
                if "DNS 服务器" in line or "DNS Servers" in line:
                    parts = line.split(":")
                    if len(parts) > 1:
                        server = parts[1].strip()
                        if server and server not in dns_servers:
                            dns_servers.append(server)
            
            return DnsConfigInfo(servers=dns_servers)
        except Exception as e:
            logger.error(f"采集DNS配置失败: {e}", extra={"trace_id": ctx.trace_id})
            return DnsConfigInfo(servers=[])

    async def _get_proxy_config(self, ctx: FlowContext) -> Optional[ProxyConfigInfo]:
        """获取代理配置"""
        return ProxyConfigInfo(enabled=False)

    async def _get_firewall_status(self, ctx: FlowContext) -> Optional[FirewallInfo]:
        """获取防火墙状态"""
        return FirewallInfo(enabled=False)

    async def _get_arp_table(self, ctx: FlowContext) -> List[ArpEntry]:
        """获取 ARP 表（含 Interface 分段，供与 CPE MAC 交叉验证）。"""
        entries: List[ArpEntry] = []
        try:
            result = run_hidden(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="ignore",
            )
            if result.returncode != 0:
                return entries

            current_scope = ""
            iface_hdr = re.compile(
                r"^(?:Interface:|接口:)\s*(\d+\.\d+\.\d+\.\d+)\s+",
                re.IGNORECASE,
            )
            row_re = re.compile(
                r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5})\s+",
            )

            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                m_if = iface_hdr.match(line)
                if m_if:
                    current_scope = m_if.group(1)
                    continue
                m_row = row_re.match(line)
                if m_row:
                    entries.append(
                        ArpEntry(
                            ip_address=m_row.group(1),
                            mac_address=m_row.group(2),
                            interface=current_scope,
                        )
                    )
        except Exception as e:
            logger.error(f"采集ARP表失败: {e}", extra={"trace_id": ctx.trace_id})
        return entries

    async def _get_ipv6_info(self, ctx: FlowContext) -> Optional[Ipv6Info]:
        """获取IPv6信息"""
        return Ipv6Info(enabled=False)

    async def _get_system_info(self, ctx: FlowContext) -> Dict[str, Any]:
        """获取系统基本信息"""
        import platform
        return {
            "hostname": platform.node(),
            "os_version": platform.platform(),
            "architecture": platform.machine(),
            "uptime_seconds": 0, # 简化处理
        }
