"""
Windows系统信息采集器

通过 ToolDispatcher 调用 WindowsSystemTool 采集系统信息，
将工具返回的 dict 转换为结构化的 SystemInfoSnapshot 对象。

遵循 SDWAN_SPEC.md §2.4 工具系统规范
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
遵循 Sprint3_plan.md 阶段3.1 配置采集器实现
"""

import logging
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.system import (
    AdapterInfo,
    AdapterStatus,
    AdapterType,
    ArpEntry,
    ConnectionInfo,
    DnsConfigInfo,
    FirewallInfo,
    IpConfigInfo,
    Ipv6Info,
    ProxyConfigInfo,
    RouteInfo,
    SystemInfoSnapshot,
)
from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.tools.registry.base import ToolDispatcher, ToolRegistry
from sdwan_desktop.tools.registry.decorator import service_function

logger = logging.getLogger(__name__)


class WindowsCollector:
    """Windows系统信息采集器

    通过 ToolDispatcher 调用 WindowsSystemTool 采集系统配置信息，
    将工具返回的原始 dict 数据转换为结构化的 SystemInfoSnapshot 对象。

    采集内容包括：
    1. 网卡适配器信息 (AdapterInfo列表)
    2. IP配置 (IpConfigInfo)
    3. 路由表 (RouteInfo列表)
    4. DNS配置 (DnsConfigInfo)
    5. 代理配置 (ProxyConfigInfo)
    6. 防火墙状态 (FirewallInfo)
    7. ARP表 (ArpEntry列表)
    8. IPv6信息 (Ipv6Info)
    9. 系统基本信息 (hostname, os_version等)

    采集失败时记录错误但不中断整体流程，返回部分数据。
    """

    def __init__(self, dispatcher: Optional[ToolDispatcher] = None):
        """初始化Windows采集器

        Args:
            dispatcher: 工具调度器，默认为使用全局ToolRegistry的实例
        """
        registry = ToolRegistry()
        self._dispatcher = dispatcher or ToolDispatcher(registry=registry)

    @service_function
    async def collect(self, ctx: FlowContext) -> SystemInfoSnapshot:
        """执行系统信息采集

        通过 ToolDispatcher 调用 WindowsSystemTool，
        将返回的 dict 数据转换为结构化的 SystemInfoSnapshot。

        Args:
            ctx: 流程上下文，包含 trace_id 等元信息

        Returns:
            SystemInfoSnapshot: 系统信息快照，包含所有采集到的数据
        """
        logger.info("开始采集Windows系统信息", extra={"trace_id": ctx.trace_id})

        # 1. 构建工具请求
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": True,
                "collect_routes": True,
                "collect_dns": True,
                "collect_proxy": True,
                "collect_firewall": True,
                "collect_arp": True,
                "collect_connections": False,
                "collect_ipv6": True,
            },
            trace_id=ctx.trace_id,
            context={"flow_id": ctx.flow_id, "flow_name": ctx.flow_name},
        )

        # 2. 通过调度器调用工具
        try:
            response: ToolResponse = await self._dispatcher.dispatch(
                tool_name="windows_system",
                request=request,
                ctx=ctx,
            )
        except Exception as e:
            logger.error(
                f"调用WindowsSystemTool失败: {e}",
                extra={"trace_id": ctx.trace_id},
                exc_info=True,
            )
            return SystemInfoSnapshot(trace_id=ctx.trace_id)

        # 3. 检查工具执行结果
        if not response.success:
            logger.error(
                f"WindowsSystemTool执行失败: {response.error_message}",
                extra={"trace_id": ctx.trace_id},
            )
            return SystemInfoSnapshot(trace_id=ctx.trace_id)

        # 4. 将工具返回的 dict 转换为结构化的 SystemInfoSnapshot
        snapshot_data = response.data or {}
        raw_snapshot = snapshot_data.get("snapshot", {})
        
        logger.debug(f"[Collector] 从响应中获取 snapshot: {type(raw_snapshot)}", extra={"trace_id": ctx.trace_id})
        if isinstance(raw_snapshot, dict):
            logger.debug(f"[Collector] snapshot keys: {raw_snapshot.keys()}", extra={"trace_id": ctx.trace_id})
            adapters_raw = raw_snapshot.get("adapters", [])
            logger.debug(f"[Collector] snapshot.adapters (dict): {len(adapters_raw)} 个", extra={"trace_id": ctx.trace_id})
            for i, a in enumerate(adapters_raw):
                logger.debug(f"[Collector] Dict Adapter {i}: {a}", extra={"trace_id": ctx.trace_id})

        snapshot = self._convert_to_snapshot(raw_snapshot, ctx.trace_id)

        logger.info(
            f"Windows系统信息采集完成: "
            f"网卡={len(snapshot.adapters)}, "
            f"路由={len(snapshot.routes)}, "
            f"ARP={len(snapshot.arp_table)}",
            extra={"trace_id": ctx.trace_id},
        )

        return snapshot

    def _convert_to_snapshot(
        self, raw: Dict[str, Any], trace_id: str
    ) -> SystemInfoSnapshot:
        """将工具返回的原始 dict 转换为 SystemInfoSnapshot

        遵循 SDWAN_SPEC_PATCHES.md PATCH-002:
        - Tool层内部允许使用dict处理第三方数据
        - 在边界处（Tool返回前）将dict转换为结构化对象

        Args:
            raw: 工具返回的原始 snapshot dict
            trace_id: 追踪ID

        Returns:
            SystemInfoSnapshot: 结构化的系统信息快照
        """
        snapshot = SystemInfoSnapshot(trace_id=trace_id)

        # 4.1 网卡适配器信息
        raw_adapters = raw.get("adapters", [])
        
        logger.debug(f"[Collector] 收到原始网卡数据: {len(raw_adapters)} 个", extra={"trace_id": trace_id})
        for i, a in enumerate(raw_adapters):
            logger.debug(f"[Collector] 原始网卡 {i}: name={a.get('name')}, is_connected={a.get('is_connected')}, ip={a.get('ip_addresses')}", extra={"trace_id": trace_id})
            
        snapshot.adapters = self._parse_adapter_list(raw_adapters)
        
        logger.debug(f"[Collector] 解析后网卡数据: {len(snapshot.adapters)} 个", extra={"trace_id": trace_id})
        for i, a in enumerate(snapshot.adapters):
            logger.debug(f"[Collector] 解析后网卡 {i}: name={a.name}, is_connected={a.is_connected}, ip={a.ip_addresses}, gw={a.default_gateway}", extra={"trace_id": trace_id})

        # 4.2 IP配置
        raw_ip_config = raw.get("ip_config")
        if raw_ip_config:
            snapshot.ip_config = self._parse_ip_config(raw_ip_config)
        else:
            # 如果工具返回中没有 ip_config，尝试从主网卡聚合信息
            primary = self._find_primary_adapter(snapshot.adapters)
            if primary:
                snapshot.ip_config = IpConfigInfo(
                    default_gateway=primary.default_gateway,
                    dns_servers=primary.dns_servers or [],
                    dhcp_enabled=primary.dhcp_enabled,
                )

        # 4.3 路由表
        raw_routes = raw.get("routes", [])
        snapshot.routes = self._parse_route_list(raw_routes)

        # 4.4 DNS配置
        raw_dns = raw.get("dns_config")
        if raw_dns:
            snapshot.dns_config = self._parse_dns_config(raw_dns)

        # 4.5 代理配置
        raw_proxy = raw.get("proxy_config")
        if raw_proxy:
            snapshot.proxy_config = self._parse_proxy_config(raw_proxy)

        # 4.6 防火墙状态
        raw_firewall = raw.get("firewall_status")
        if raw_firewall:
            snapshot.firewall_status = self._parse_firewall_status(raw_firewall)

        # 4.7 ARP表
        raw_arp = raw.get("arp_table", [])
        snapshot.arp_table = self._parse_arp_list(raw_arp)

        # 4.8 活动连接
        raw_connections = raw.get("active_connections", [])
        if raw_connections:
            snapshot.active_connections = self._parse_connection_list(raw_connections)

        # 4.9 IPv6信息
        raw_ipv6 = raw.get("ipv6")
        if raw_ipv6:
            snapshot.ipv6 = self._parse_ipv6_info(raw_ipv6)

        return snapshot

    def _parse_adapter_list(self, raw_adapters: List[Dict[str, Any]]) -> List[AdapterInfo]:
        """解析网卡适配器列表"""
        adapters = []
        for raw in raw_adapters:
            try:
                adapter = AdapterInfo(
                    name=raw.get("name", ""),
                    description=raw.get("description", ""),
                    mac_address=raw.get("mac_address", ""),
                    adapter_type=self._parse_adapter_type(raw.get("adapter_type", "ethernet")),
                    status=self._parse_adapter_status(raw.get("status", "unknown")),
                    is_connected=raw.get("is_connected", False),
                    speed_mbps=raw.get("speed_mbps"),
                    ip_addresses=raw.get("ip_addresses", []),
                    ip_subnets=raw.get("ip_subnets", []),
                    default_gateway=raw.get("default_gateway"),
                    dhcp_enabled=raw.get("dhcp_enabled", False),
                    dns_servers=raw.get("dns_servers", []),
                    dns_suffix=raw.get("dns_suffix"),
                    mtu=raw.get("mtu", 1500),
                )
                adapters.append(adapter)
            except Exception as e:
                logger.warning(f"解析单个网卡配置失败: {e}", extra={"trace_id": "collector"})
        return adapters

    def _find_primary_adapter(self, adapters: List[AdapterInfo]) -> Optional[AdapterInfo]:
        """查找主网卡（有默认网关且已连接的网卡）"""
        for adapter in adapters:
            if adapter.is_connected and adapter.default_gateway:
                return adapter
        # 如果没有找到有网关的，返回第一个已连接的
        for adapter in adapters:
            if adapter.is_connected:
                return adapter
        return None

    def _parse_adapter_type(self, type_str: str) -> AdapterType:
        """解析网卡类型字符串为枚举"""
        type_map = {
            "ethernet": AdapterType.ETHERNET,
            "wifi": AdapterType.WIFI,
            "loopback": AdapterType.LOOPBACK,
            "tunnel": AdapterType.TUNNEL,
            "virtual": AdapterType.VIRTUAL,
        }
        return type_map.get(type_str.lower(), AdapterType.ETHERNET)

    def _parse_adapter_status(self, status_str: str) -> AdapterStatus:
        """解析网卡状态字符串为枚举"""
        status_map = {
            "connected": AdapterStatus.CONNECTED,
            "disconnected": AdapterStatus.DISCONNECTED,
            "unknown": AdapterStatus.UNKNOWN,
        }
        return status_map.get(status_str.lower(), AdapterStatus.UNKNOWN)

    def _parse_ip_config(self, raw: Dict[str, Any]) -> IpConfigInfo:
        """解析IP配置"""
        return IpConfigInfo(
            default_gateway=raw.get("default_gateway"),
            dns_servers=raw.get("dns_servers", []),
            dhcp_enabled=raw.get("dhcp_enabled", False),
        )

    def _parse_route_list(self, raw_routes: List[Dict[str, Any]]) -> List[RouteInfo]:
        """解析路由表"""
        routes = []
        for raw in raw_routes:
            try:
                route = RouteInfo(
                    destination=raw.get("destination", ""),
                    netmask=raw.get("netmask", ""),
                    gateway=raw.get("gateway", ""),
                    interface=raw.get("interface", ""),
                    metric=raw.get("metric", 0),
                )
                routes.append(route)
            except Exception as e:
                logger.warning(f"解析单个路由项失败: {e}", extra={"trace_id": "collector"})
        return routes

    def _parse_dns_config(self, raw: Dict[str, Any]) -> DnsConfigInfo:
        """解析DNS配置"""
        return DnsConfigInfo(servers=raw.get("servers", []))

    def _parse_proxy_config(self, raw: Dict[str, Any]) -> ProxyConfigInfo:
        """解析代理配置"""
        return ProxyConfigInfo(enabled=raw.get("enabled", False))

    def _parse_firewall_status(self, raw: Dict[str, Any]) -> FirewallInfo:
        """解析防火墙状态"""
        return FirewallInfo(enabled=raw.get("enabled", False))

    def _parse_arp_list(self, raw_arp: List[Dict[str, Any]]) -> List[ArpEntry]:
        """解析ARP表"""
        entries = []
        for raw in raw_arp:
            try:
                entry = ArpEntry(
                    ip_address=raw.get("ip_address", ""),
                    mac_address=raw.get("mac_address", ""),
                )
                entries.append(entry)
            except Exception as e:
                logger.warning(f"解析单个ARP项失败: {e}", extra={"trace_id": "collector"})
        return entries

    def _parse_connection_list(self, raw_connections: List[Dict[str, Any]]) -> List[ConnectionInfo]:
        """解析活动连接"""
        connections = []
        for raw in raw_connections:
            try:
                conn = ConnectionInfo(
                    local_address=raw.get("local_address", ""),
                    remote_address=raw.get("remote_address", ""),
                    state=raw.get("state", ""),
                )
                connections.append(conn)
            except Exception as e:
                logger.warning(f"解析单个连接项失败: {e}", extra={"trace_id": "collector"})
        return connections

    def _parse_ipv6_info(self, raw: Dict[str, Any]) -> Ipv6Info:
        """解析IPv6信息"""
        return Ipv6Info(enabled=raw.get("enabled", False))

