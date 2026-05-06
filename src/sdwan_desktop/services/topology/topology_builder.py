"""
拓扑构建服务

从 PC 和 CPE 配置数据构建网络拓扑，识别 NAT 转换。
遵循 SDWAN_SPEC.md §2.5 拓扑构建规范
"""

import logging
from typing import Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, InterfaceInfo
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.topology.topology import (
    Edge,
    LinkType,
    NetworkTopology,
    Node,
    NodeType,
)

logger = logging.getLogger(__name__)


class TopologyBuilder:
    """拓扑构建器
    
    从 PC 采集数据和 CPE 配置中构建网络拓扑图。
    
    工作流程：
    1. 创建 PC 节点（从 Windows 采集数据）
    2. 创建 CPE 节点（从 CpeConfiguration）
    3. 识别网关和 Hub 节点（从路由表和隧道信息）
    4. 构建链路关系（PC→CPE→GW→Hub）
    5. 检测 NAT 转换（从 NAT 规则表）
    
    输出：
    - NetworkTopology 对象（包含节点和链路）
    """
    
    def build(
        self,
        pc_data: dict,
        cpe_result: CollectorResult,
    ) -> NetworkTopology:
        """构建网络拓扑
        
        Args:
            pc_data: PC 采集数据（来自 WindowsCollector）
            cpe_result: CPE 采集结果（包含 CpeConfiguration）
            
        Returns:
            网络拓扑对象
        """
        topology = NetworkTopology()
        
        # 1. 创建 PC 节点
        pc_node = self._build_pc_node(pc_data)
        topology.add_node(pc_node)
        
        # 2. 创建 CPE 节点
        if not cpe_result.success or "cpe_configuration" not in cpe_result.data:
            logger.warning("CPE 配置采集失败，跳过 CPE 节点构建")
            return topology
        
        cpe_config = cpe_result.data["cpe_configuration"]
        cpe_node = self._build_cpe_node(cpe_config)
        topology.add_node(cpe_node)
        
        # 3. 构建 PC → CPE 链路
        pc_cpe_edge = self._build_pc_to_cpe_edge(pc_node, cpe_node, pc_data)
        if pc_cpe_edge:
            topology.add_edge(pc_cpe_edge)
        
        # 4. 识别并创建网关节点
        gateway_node = self._build_gateway_node(cpe_config)
        if gateway_node:
            topology.add_node(gateway_node)
            
            # 构建 CPE → Gateway 链路
            cpe_gw_edge = self._build_cpe_to_gateway_edge(cpe_node, gateway_node, cpe_config)
            if cpe_gw_edge:
                topology.add_edge(cpe_gw_edge)
        
        # 5. 识别并创建 Hub 节点（从 VPN 隧道）
        hub_node = self._build_hub_node(cpe_config)
        if hub_node:
            topology.add_node(hub_node)
            
            # 构建 CPE → Hub 链路（隧道）
            cpe_hub_edge = self._build_cpe_to_hub_edge(cpe_node, hub_node, cpe_config)
            if cpe_hub_edge:
                topology.add_edge(cpe_hub_edge)
        
        # 6. 检测 NAT 转换
        self._detect_nat_traversal(topology, cpe_config)
        
        logger.info(
            f"拓扑构建完成: {len(topology.nodes)} 个节点, {len(topology.edges)} 条链路"
        )
        
        return topology
    
    def _build_pc_node(self, pc_data: dict) -> Node:
        """构建 PC 节点
        
        Args:
            pc_data: PC 采集数据
            
        Returns:
            PC 节点对象
        """
        hostname = pc_data.get("hostname", "unknown-pc")
        ip_address = pc_data.get("primary_ip", None)
        interfaces = pc_data.get("interfaces", [])
        
        return Node(
            id="pc-001",
            name=hostname,
            node_type=NodeType.PC,
            ip_address=ip_address,
            interfaces=interfaces,
            metadata={"os": pc_data.get("os", "unknown")},
        )
    
    def _build_cpe_node(self, cpe_config: CpeConfiguration) -> Node:
        """构建 CPE 节点
        
        Args:
            cpe_config: CPE 配置对象
            
        Returns:
            CPE 节点对象
        """
        # 获取 WAN 接口的 IP 作为主 IP
        wan_ips = [iface.ip_address for iface in cpe_config.wan_interfaces if iface.ip_address]
        primary_ip = wan_ips[0] if wan_ips else None
        
        # 收集所有接口 IP
        all_ips = [
            iface.ip_address for iface in cpe_config.interfaces if iface.ip_address
        ]
        
        return Node(
            id="cpe-001",
            name=cpe_config.hostname or "unknown-cpe",
            node_type=NodeType.CPE,
            ip_address=primary_ip,
            vendor=cpe_config.vendor,
            model=cpe_config.model,
            interfaces=all_ips,
            metadata={
                "version": cpe_config.version,
                "wan_count": len(cpe_config.wan_interfaces),
                "lan_count": len(cpe_config.lan_interfaces),
            },
        )
    
    def _build_gateway_node(self, cpe_config: CpeConfiguration) -> Optional[Node]:
        """构建网关节点
        
        从默认路由中提取网关信息。
        
        Args:
            cpe_config: CPE 配置对象
            
        Returns:
            网关节点对象，如果无法识别返回 None
        """
        default_route = cpe_config.default_route
        if not default_route:
            logger.warning("未找到默认路由，跳过网关节点构建")
            return None
        
        gateway_ip = default_route.gateway
        if not gateway_ip:
            logger.warning("默认路由没有网关地址，跳过网关节点构建")
            return None
        
        return Node(
            id="gw-001",
            name=f"Gateway ({gateway_ip})",
            node_type=NodeType.GATEWAY,
            ip_address=gateway_ip,
            interfaces=[gateway_ip],
            metadata={
                "route_protocol": default_route.protocol,
                "route_metric": default_route.metric,
            },
        )
    
    def _build_hub_node(self, cpe_config: CpeConfiguration) -> Optional[Node]:
        """构建 Hub 节点
        
        从 VPN 隧道中提取 Hub 信息（第一个 active 隧道的远端）。
        
        Args:
            cpe_config: CPE 配置对象
            
        Returns:
            Hub 节点对象，如果没有活跃隧道返回 None
        """
        active_tunnels = [
            tunnel for tunnel in cpe_config.vpn_tunnels
            if tunnel.state == "up"
        ]
        
        if not active_tunnels:
            logger.warning("没有活跃的 VPN 隧道，跳过 Hub 节点构建")
            return None
        
        # 使用第一个活跃隧道的远端作为 Hub
        first_tunnel = active_tunnels[0]
        hub_ip = first_tunnel.remote_ip
        
        return Node(
            id="hub-001",
            name=f"Hub ({hub_ip})",
            node_type=NodeType.HUB,
            ip_address=hub_ip,
            interfaces=[hub_ip],
            metadata={},
        )
    
    def _build_pc_to_cpe_edge(
        self,
        pc_node: Node,
        cpe_node: Node,
        pc_data: dict,
    ) -> Optional[Edge]:
        """构建 PC → CPE 链路
        
        Args:
            pc_node: PC 节点
            cpe_node: CPE 节点
            pc_data: PC 采集数据
            
        Returns:
            链路对象，如果无法构建返回 None
        """
        pc_ip = pc_node.ip_address
        cpe_ip = cpe_node.ip_address
        
        if not pc_ip or not cpe_ip:
            logger.warning("PC 或 CPE 缺少 IP 地址，无法构建链路")
            return None
        
        return Edge(
            id="link-pc-cpe",
            source_id=pc_node.id,
            target_id=cpe_node.id,
            link_type=LinkType.PHYSICAL,
            source_interface=pc_ip,
            target_interface=cpe_ip,
            metadata={"description": "PC to CPE connection"},
        )
    
    def _build_cpe_to_gateway_edge(
        self,
        cpe_node: Node,
        gateway_node: Node,
        cpe_config: CpeConfiguration,
    ) -> Optional[Edge]:
        """构建 CPE → Gateway 链路
        
        Args:
            cpe_node: CPE 节点
            gateway_node: 网关节点
            cpe_config: CPE 配置对象
            
        Returns:
            链路对象，如果无法构建返回 None
        """
        # 查找连接到网关的 CPE 接口
        default_route = cpe_config.default_route
        if not default_route:
            return None
        
        cpe_interface_ip = self._find_interface_for_route(
            cpe_config.interfaces, default_route
        )
        
        return Edge(
            id="link-cpe-gw",
            source_id=cpe_node.id,
            target_id=gateway_node.id,
            link_type=LinkType.PHYSICAL,
            source_interface=cpe_interface_ip,
            target_interface=gateway_node.ip_address,
            metadata={
                "route_protocol": default_route.protocol,
                "description": "CPE to Gateway connection",
            },
        )
    
    def _build_cpe_to_hub_edge(
        self,
        cpe_node: Node,
        hub_node: Node,
        cpe_config: CpeConfiguration,
    ) -> Optional[Edge]:
        """构建 CPE → Hub 链路（隧道）
        
        Args:
            cpe_node: CPE 节点
            hub_node: Hub 节点
            cpe_config: CPE 配置对象
            
        Returns:
            链路对象，如果无法构建返回 None
        """
        active_tunnels = [
            tunnel for tunnel in cpe_config.vpn_tunnels
            if tunnel.state == "up" and tunnel.remote_ip == hub_node.ip_address
        ]
        
        if not active_tunnels:
            return None
        
        first_tunnel = active_tunnels[0]
        
        # 查找隧道的本地接口
        local_interface_ip = self._find_tunnel_local_interface(
            cpe_config.interfaces, first_tunnel
        )
        
        return Edge(
            id="link-cpe-hub",
            source_id=cpe_node.id,
            target_id=hub_node.id,
            link_type=LinkType.TUNNEL,
            source_interface=local_interface_ip,
            target_interface=hub_node.ip_address,
            metadata={
                "tunnel_type": first_tunnel.type,
                "local_color": first_tunnel.local_color,
                "description": "CPE to Hub tunnel",
            },

        )
    
    def _detect_nat_traversal(
        self,
        topology: NetworkTopology,
        cpe_config: CpeConfiguration,
    ):
        """检测 NAT 转换
        
        从 CPE 的 NAT 规则表中识别是否存在 NAT 转换，并标记相关链路。
        
        Args:
            topology: 网络拓扑对象（会被修改）
            cpe_config: CPE 配置对象
        """
        if not cpe_config.nat_rules:
            logger.debug("没有 NAT 规则，跳过 NAT 检测")
            return
        
        # 遍历所有链路，检查是否涉及 NAT
        for edge in topology.edges:
            # 检查源地址是否在 NAT 规则中
            for nat_rule in cpe_config.nat_rules:
                if edge.source_interface == nat_rule.inside_addr:
                    edge.is_nat = True
                    edge.nat_source = nat_rule.inside_addr
                    edge.nat_destination = nat_rule.outside_addr
                    logger.info(
                        f"检测到 NAT 转换: {edge.nat_source} → {edge.nat_destination}"
                    )
                    break
    
    def _find_interface_for_route(
        self,
        interfaces: list[InterfaceInfo],
        route,
    ) -> Optional[str]:
        """查找路由对应的接口 IP
        
        Args:
            interfaces: 接口列表
            route: 路由条目
            
        Returns:
            接口 IP，如果找不到返回 None
        """
        if not route.interface:
            return None
        
        for iface in interfaces:
            if iface.name == route.interface and iface.ip_address:
                return iface.ip_address
        
        return None
    
    def _find_tunnel_local_interface(
        self,
        interfaces: list[InterfaceInfo],
        tunnel,
    ) -> Optional[str]:
        """查找隧道对应的本地接口 IP
        
        Args:
            interfaces: 接口列表
            tunnel: VPN 隧道信息
            
        Returns:
            接口 IP，如果找不到返回 None
        """
        # 简化实现：返回第一个 WAN 接口的 IP
        for iface in interfaces:
            if iface.ip_address and "wan" in iface.name.lower():
                return iface.ip_address
        
        # fallback：返回第一个有 IP 的接口
        for iface in interfaces:
            if iface.ip_address:
                return iface.ip_address
        
        return None
