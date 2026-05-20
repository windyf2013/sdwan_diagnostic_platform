"""
拓扑构建服务

从 PC 和 CPE 配置数据构建网络拓扑，识别 NAT 转换。
遵循 SDWAN_SPEC.md §2.5 拓扑构建规范
"""

import ipaddress
import logging
import re
from typing import Optional, Tuple

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


def _humanize_cpe_vendor(vendor_id: Optional[str]) -> Optional[str]:
    """将内部 vendor 标识转为展示用厂商名。"""
    if not vendor_id:
        return None
    if vendor_id == "raisecom_msg5200b":
        return "Raisecom (MSG5200B)"
    if vendor_id == "raisecom_msg5200d":
        return "Raisecom (MSG5200D)"
    if vendor_id == "raisecom_msg5200":
        return "Raisecom (MSG5200A)"
    return vendor_id


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
        cpe_mgmt_ip: Optional[str] = None,
    ) -> NetworkTopology:
        """构建网络拓扑
        
        Args:
            pc_data: PC 采集数据（来自 WindowsCollector）
            cpe_result: CPE 采集结果（包含 CpeConfiguration）
            cpe_mgmt_ip: 本会话探测使用的 CPE 管理地址（通常为 CLI ``--cpe``）。
                在缺少二层附着证据但采集成功时，用于绘制 ``PC→CPE`` 的逻辑链路
            
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
        
        # 3. 构建 PC → CPE（双轨）：ARP/MAC → physical；若无证据但采集成功 → logical。
        mgmt = (cpe_mgmt_ip or "").strip()
        pc_cpe_edge = self._build_pc_to_cpe_edge(pc_node, cpe_node, pc_data, cpe_config)
        if pc_cpe_edge:
            topology.add_edge(pc_cpe_edge)
        else:
            log_edge = self._build_pc_to_cpe_logical_reachability_edge(
                pc_node, cpe_node, pc_data, mgmt
            )
            if log_edge:
                topology.add_edge(log_edge)
                topology.notes.append(
                    "PC→CPE：无 CPE ARP/本机网关 MAC 与 CPE 接口交叉证据；"
                    "已根据本会话采集成功绘制逻辑可达链路（不等于二层同 LAN）。"
                )
            elif pc_node.ip_address:
                topology.notes.append(
                    "PC→CPE 链路未绘制：CPE ARP 中无本机 IPv4，且本机默认网关 MAC 与 CPE 各接口 MAC 不一致，"
                    "且无法认定采集会话目标；若默认网关不是本 CPE 的三层地址，属正常现象。"
                )
        
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
            metadata={
                "os": pc_data.get("os", "unknown"),
                "primary_interface": pc_data.get("primary_interface", ""),
            },
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
        
        wan_ifaces = cpe_config.wan_interfaces
        wan_names = {i.name for i in wan_ifaces}
        lan_ifaces = [i for i in cpe_config.lan_interfaces if i.name not in wan_names]

        def _iface_summary(ifaces: list) -> str:
            if not ifaces:
                return "—"
            return "、".join(
                f"{i.name}({i.ip_address or '无 IP'})" for i in ifaces[:10]
            )

        return Node(
            id="cpe-001",
            name=cpe_config.hostname or "unknown-cpe",
            node_type=NodeType.CPE,
            ip_address=primary_ip,
            vendor=_humanize_cpe_vendor(cpe_config.vendor),
            model=cpe_config.model,
            interfaces=all_ips,
            metadata={
                "vendor_id": cpe_config.vendor,
                "version": cpe_config.version,
                "wan_ports": _iface_summary(wan_ifaces),
                "lan_ports": _iface_summary(lan_ifaces),
                "interface_total": len(cpe_config.interfaces),
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
        eligible = [
            tunnel for tunnel in cpe_config.vpn_tunnels
            if tunnel.state != "down"
        ]
        
        if not eligible:
            logger.warning("没有可用的 VPN 隧道（全部为 Down），跳过 Hub 节点构建")
            return None
        
        # 使用第一条可用隧道的远端作为 Hub（含 unknown：仅凭配置推断对端）
        first_tunnel = eligible[0]
        hub_ip = first_tunnel.remote_ip
        
        return Node(
            id="hub-001",
            name=f"Hub ({hub_ip})",
            node_type=NodeType.HUB,
            ip_address=hub_ip,
            interfaces=[hub_ip],
            metadata={},
        )
    
    def _ipv4_same_slash24(self, a: Optional[str], b: Optional[str]) -> bool:
        """判断两 IPv4 是否落在同一 /24（用于报告层二邻接语义，非严格掩码匹配）。"""
        if not a or not b:
            return False
        try:
            pa = ipaddress.ip_address(a)
            pb = ipaddress.ip_address(b)
            if not isinstance(pa, ipaddress.IPv4Address) or not isinstance(pb, ipaddress.IPv4Address):
                return False
            return (int(pa) >> 8) == (int(pb) >> 8)
        except ValueError:
            return False

    def _norm_mac(self, mac: Optional[str]) -> str:
        """将常见 MAC 表示归一为 12 位小写十六进制（无分隔符）。"""
        if not mac:
            return ""
        s = mac.strip().lower().replace("-", "").replace(":", "").replace(".", "")
        if len(s) == 12 and all(c in "0123456789abcdef" for c in s):
            return s
        return ""

    def _find_cpe_interface_by_name(
        self,
        cpe_config: CpeConfiguration,
        arp_ifname: str,
    ) -> Optional[InterfaceInfo]:
        target = (arp_ifname or "").strip().lower()
        if not target:
            return None
        for iface in cpe_config.interfaces:
            if (iface.name or "").strip().lower() == target:
                return iface
        return None

    def _select_cpe_attachment_for_pc(
        self,
        pc_ip: str,
        pc_data: Optional[dict],
        cpe_config: CpeConfiguration,
    ) -> Tuple[Optional[str], str, bool, str]:
        """依据 ARP 证据选择 CPE 附着点；无法证明则返回 (None, '', False, '')。

        1) CPE ``show arp`` 中存在与 PC 相同的 IPv4 → 取 Interface 列对应本地三层接口；
        2) PC ``arp -a`` 中默认网关 IP 的 MAC 与 CPE 某接口 MAC 一致 → 三层直连于该接口。

        不使用同网段猜选或 WAN/LAN 启发式。
        """
        pc_data = pc_data or {}
        evidence = ""

        for entry in cpe_config.arp_entries or []:
            if (entry.ip_address or "").strip() != (pc_ip or "").strip():
                continue
            iface = self._find_cpe_interface_by_name(cpe_config, entry.interface or "")
            if iface and iface.ip_address:
                evidence = "cpe_arp"
                return (
                    iface.ip_address,
                    iface.name or "",
                    self._ipv4_same_slash24(pc_ip, iface.ip_address),
                    evidence,
                )
            logger.warning(
                "CPE ARP 含本机 IP %s 但接口名 %s 在已解析接口中未匹配",
                pc_ip,
                entry.interface,
            )

        gw = (pc_data.get("default_gateway") or "").strip()
        if gw:
            pc_gw_mac = ""
            for row in pc_data.get("arp_table") or []:
                if not isinstance(row, dict):
                    continue
                if (row.get("ip_address") or "").strip() == gw:
                    pc_gw_mac = self._norm_mac(row.get("mac_address"))
                    break
            if pc_gw_mac:
                for iface in cpe_config.interfaces:
                    if self._norm_mac(iface.mac_address) == pc_gw_mac and iface.ip_address:
                        evidence = "pc_arp_gateway_mac"
                        return (
                            iface.ip_address,
                            iface.name or "",
                            self._ipv4_same_slash24(pc_ip, iface.ip_address),
                            evidence,
                        )

        return None, "", False, ""

    def _build_pc_to_cpe_edge(
        self,
        pc_node: Node,
        cpe_node: Node,
        pc_data: dict,
        cpe_config: CpeConfiguration,
    ) -> Optional[Edge]:
        """构建 PC → CPE 链路
        
        Args:
            pc_node: PC 节点
            cpe_node: CPE 节点
            pc_data: PC 采集数据
            cpe_config: CPE 配置（用于选择同网段附着接口）
            
        Returns:
            链路对象，如果无法构建返回 None
        """
        pc_ip = pc_node.ip_address
        if not pc_ip:
            logger.warning("PC 缺少 IP 地址，无法构建链路")
            return None

        cpe_ip, cpe_iface, same24, evidence = self._select_cpe_attachment_for_pc(pc_ip, pc_data, cpe_config)
        if not cpe_ip:
            logger.debug(
                "未构建 PC→CPE PHY 链路：无 ARP 证据（CPE ARP 无本机 %s，且默认网关 MAC 与 CPE 接口 MAC 不匹配）；"
                "若采集成功仍可尝试 LOGICAL 链路。",
                pc_ip,
            )
            return None

        pc_iface = (pc_data or {}).get("primary_interface", "") or ""

        return Edge(
            id="link-pc-cpe",
            source_id=pc_node.id,
            target_id=cpe_node.id,
            link_type=LinkType.PHYSICAL,
            source_interface=pc_ip,
            target_interface=cpe_ip,
            metadata={
                "description": "PC to CPE connection",
                "source_interface_name": pc_iface,
                "target_interface_name": cpe_iface,
                "same_subnet_slash24": same24,
                "adjacency_evidence": evidence,
            },
        )

    def _build_pc_to_cpe_logical_reachability_edge(
        self,
        pc_node: Node,
        cpe_node: Node,
        pc_data: dict,
        cpe_mgmt_ip: str,
    ) -> Optional[Edge]:
        """无二层附着证据时，仅当给定 CPE 管理地址且在流程内已成功采集时才画 logical 可达边。"""
        pc_ip = pc_node.ip_address
        if not pc_ip or not cpe_mgmt_ip:
            logger.info(
                "未绘制 PC→CPE 逻辑链路：缺少 PC IPv4 (%s) 或 cpe_mgmt_ip（%s）",
                pc_ip,
                cpe_mgmt_ip,
            )
            return None
        pc_iface = (pc_data or {}).get("primary_interface", "") or ""
        slash24_ok = self._ipv4_same_slash24(pc_ip, cpe_mgmt_ip)
        return Edge(
            id="link-pc-cpe-logical",
            source_id=pc_node.id,
            target_id=cpe_node.id,
            link_type=LinkType.LOGICAL,
            source_interface=pc_ip,
            target_interface=cpe_mgmt_ip,
            metadata={
                "description": (
                    "PC to CPE management reachability (session success; L2 attachment not proven)"
                ),
                "source_interface_name": pc_iface,
                "target_interface_name": "management",
                "same_subnet_slash24": slash24_ok,
                "adjacency_evidence": "session_reachable",
                "subnet_alignment_note": (
                    "/24 同段（推断）：PC 与 CPE 管理地址"
                    if slash24_ok
                    else "采集路径与 PC 主地址非同 /24（推断）；不表示不可达或非邻接。"
                ),
            },
        )

    def _arp_gateway_on_egress_iface(
        self,
        cpe_config: CpeConfiguration,
        gateway_ip: str,
        egress_iface: str,
    ) -> bool:
        """ARP 是否在出接口上解析到默认网关 IPv4。"""
        if not gateway_ip or not egress_iface:
            return False
        eg = egress_iface.strip().lower()
        for entry in cpe_config.arp_entries or []:
            if (entry.ip_address or "").strip() != gateway_ip.strip():
                continue
            if (entry.interface or "").strip().lower() == eg:
                return True
        return False

    def _gateway_on_explicit_subnet_route_on_iface(
        self,
        cpe_iface_ip: Optional[str],
        gateway_ip: str,
        egress_iface: str,
        routes: list,
    ) -> bool:
        """两 IPv4 是否同属某条出自 egress 的非默认前缀（前缀长度不少于 /24，降低误把广域 SUMMARY 当属地网段的概率）。"""
        if not cpe_iface_ip or not gateway_ip or not egress_iface:
            return False
        try:
            a = ipaddress.ip_address(cpe_iface_ip)
            b = ipaddress.ip_address(gateway_ip)
        except ValueError:
            return False
        if not isinstance(a, ipaddress.IPv4Address) or not isinstance(b, ipaddress.IPv4Address):
            return False
        ef = egress_iface.strip().lower()
        for route in routes or []:
            if (route.interface or "").strip().lower() != ef:
                continue
            dest = route.destination or ""
            if "/" not in dest or dest.startswith("0.0.0.0/"):
                continue
            try:
                net = ipaddress.ip_network(dest, strict=False)
            except ValueError:
                continue
            if net.version != 4 or net.prefixlen < 24:
                continue
            if a in net and b in net:
                return True
        return False

    def _classify_cpe_gateway_link(
        self,
        cpe_config: CpeConfiguration,
        cpe_interface_ip: Optional[str],
        gateway_ip: str,
        egress_iface: Optional[str],
    ) -> Tuple[LinkType, str]:
        """根据 ARP / connected 前缀 / /24 启发式决定对默认下一跳的链路语义。"""
        if not egress_iface:
            return LinkType.LOGICAL, "route_only"
        slash24_ok = self._ipv4_same_slash24(cpe_interface_ip, gateway_ip)
        if self._arp_gateway_on_egress_iface(cpe_config, gateway_ip, egress_iface):
            return LinkType.PHYSICAL, "cpe_arp_gateway"
        if self._gateway_on_explicit_subnet_route_on_iface(
            cpe_interface_ip, gateway_ip, egress_iface, cpe_config.routes
        ):
            return LinkType.PHYSICAL, "explicit_subnet_route"
        if slash24_ok:
            return LinkType.PHYSICAL, "slash24_heuristic"
        return LinkType.LOGICAL, "route_only"
    
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
        gw_ip = gateway_node.ip_address or ""
        egress_iface = default_route.interface or ""
        gw_link_kind, gw_evidence = self._classify_cpe_gateway_link(
            cpe_config, cpe_interface_ip, gw_ip, egress_iface or None
        )
        subnet_slash24 = self._ipv4_same_slash24(cpe_interface_ip, gw_ip)
        return Edge(
            id="link-cpe-gw",
            source_id=cpe_node.id,
            target_id=gateway_node.id,
            link_type=gw_link_kind,
            source_interface=cpe_interface_ip,
            target_interface=gw_ip,
            metadata={
                "route_protocol": default_route.protocol,
                "source_interface_name": egress_iface,
                "target_interface_name": "gateway",
                "same_subnet_slash24": subnet_slash24,
                "adjacency_evidence": gw_evidence,
                "description": "CPE to default route next-hop",
                "subnet_alignment_note": {
                    "cpe_arp_gateway": "CPE ARP：下一跳已在出接口上解析",
                    "explicit_subnet_route": "路由表：出接口上与下一跳同属某条显式前缀（≥/24）",
                    "slash24_heuristic": "同源 /24（推断）；无 ARP/显式前缀佐证",
                    "route_only": "仅默认路由语义；未发现 on-link ARP / 同源显式前缀 / 同源 /24 推断",
                }.get(gw_evidence, gw_evidence),
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
        eligible = [
            tunnel for tunnel in cpe_config.vpn_tunnels
            if tunnel.state != "down" and tunnel.remote_ip == hub_node.ip_address
        ]
        
        if not eligible:
            return None
        
        first_tunnel = eligible[0]
        
        # 查找隧道的本地接口
        local_interface_ip, local_interface_name = self._find_tunnel_local_interface(
            cpe_config, first_tunnel
        )

        overlay_segment_peer = self._vxlan_segment_peer_ip(
            local_interface_ip, cpe_config.routes
        )
        dr = cpe_config.default_route
        wan_ip = self._find_interface_for_route(cpe_config.interfaces, dr) if dr else None
        underlay_next = dr.gateway if dr else None
        underlay_iface = (dr.interface or "") if dr else ""

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
                "source_interface_name": local_interface_name,
                "description": "CPE to Hub tunnel",
                "overlay_local_ip": local_interface_ip,
                "overlay_local_iface": local_interface_name,
                "overlay_segment_peer_ip": overlay_segment_peer,
                "overlay_tunnel_peer_ip": hub_node.ip_address,
                "overlay_segment_same_subnet": self._ipv4_same_slash24(
                    local_interface_ip, overlay_segment_peer
                ) if overlay_segment_peer else False,
                "underlay_wan_ip": wan_ip,
                "underlay_wan_iface": underlay_iface,
                "underlay_next_hop_ip": underlay_next,
                "underlay_same_subnet": self._ipv4_same_slash24(wan_ip, underlay_next)
                if wan_ip and underlay_next
                else False,
            },

        )

    def _vxlan_segment_peer_ip(
        self,
        local_vxlan_ip: Optional[str],
        routes: list,
    ) -> Optional[str]:
        """从已连接路由中推断 vxlan 接口所在前缀上的对端主机地址（如 /30 另一端）。"""
        if not local_vxlan_ip:
            return None
        try:
            lip = ipaddress.ip_address(local_vxlan_ip)
        except ValueError:
            return None
        for route in routes or []:
            iface = (route.interface or "").lower()
            if not iface.startswith("vxlan"):
                continue
            dest = route.destination or ""
            if "/" not in dest:
                continue
            try:
                net = ipaddress.ip_network(dest, strict=False)
            except ValueError:
                continue
            if lip not in net:
                continue
            for addr in net:
                if addr in (net.network_address, net.broadcast_address):
                    continue
                if addr != lip:
                    return str(addr)
        return None
    
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
        cpe_config: CpeConfiguration | list[InterfaceInfo],
        tunnel,
    ) -> tuple[Optional[str], str]:
        """查找隧道对应的本地接口 IP
        
        Args:
            cpe_config: CPE 配置
            tunnel: VPN 隧道信息
            
        Returns:
            (接口IP, 接口名)
        """
        if isinstance(cpe_config, list):
            interfaces = cpe_config
            cpe_routes = []
            running_config = ""
        else:
            interfaces = cpe_config.interfaces
            cpe_routes = cpe_config.routes
            running_config = cpe_config.raw_outputs.get("show running-config", "")

        bind_name, bind_ip = self._resolve_vxlan_bind_local_ip(
            running_config,
            tunnel.local_color,
        )
        if bind_ip:
            return bind_ip, bind_name

        # 兜底：找 vxlan 路由上的本地 /32（例如 K>* 8.1.3.2/32 is directly connected, vxlan5）
        for route in cpe_routes:
            iface_name = (route.interface or "").lower()
            if iface_name.startswith("vxlan") and route.destination.endswith("/32"):
                ip = route.destination.split("/")[0]
                return ip, route.interface or "vxlan"

        # 再兜底：返回首个 WAN 或任一 IP
        for iface in interfaces:
            if iface.ip_address and ("wan" in iface.name.lower() or iface.name.lower().startswith(("ge", "xge"))):
                return iface.ip_address, iface.name
        for iface in interfaces:
            if iface.ip_address:
                return iface.ip_address, iface.name

        return None, ""

    def _resolve_vxlan_bind_local_ip(self, running_config: str, tunnel_name: str) -> tuple[str, Optional[str]]:
        """从 running-config 中解析 tunnel 绑定的 vxlan 接口及本地 IP。"""
        if not running_config or not tunnel_name:
            return "", None

        # interface vxlan5 ... bind tunnel1_5 ... ip address 8.1.3.2/30
        pattern = (
            r"interface\s+(vxlan\S+)\s*\n"
            r"(?:.*?\n)*?\s*bind\s+"
            + re.escape(tunnel_name)
            + r"\s*\n"
            r"(?:.*?\n)*?\s*ip address\s+(\d+\.\d+\.\d+\.\d+)"
        )
        match = re.search(pattern, running_config, re.IGNORECASE)
        if match:
            return match.group(1), match.group(2)

        # 仅找到绑定接口但无 ip address
        bind_only_pattern = (
            r"interface\s+(vxlan\S+)\s*\n"
            r"(?:.*?\n)*?\s*bind\s+" + re.escape(tunnel_name) + r"\b"
        )
        match = re.search(bind_only_pattern, running_config, re.IGNORECASE)
        if match:
            return match.group(1), None

        return "", None
