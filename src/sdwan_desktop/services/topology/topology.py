"""
网络拓扑数据模型

定义网络拓扑中的节点、链路和整体结构。
遵循 SDWAN_SPEC.md §2.5 拓扑构建规范
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class NodeType(Enum):
    """节点类型枚举"""
    PC = "pc"
    """PC 终端"""
    CPE = "cpe"
    """CPE 设备"""
    GATEWAY = "gateway"
    """网关"""
    HUB = "hub"
    """Hub 中心节点"""
    UNKNOWN = "unknown"
    """未知类型"""


class LinkType(Enum):
    """链路类型枚举"""
    PHYSICAL = "physical"
    """物理链路"""
    TUNNEL = "tunnel"
    """隧道链路（IPsec/GRE）"""
    LOGICAL = "logical"
    """逻辑链路（路由可达）"""


@dataclass(slots=True)
class Node:
    """拓扑节点
    
    Attributes:
        id: 节点唯一标识
        name: 节点名称（主机名或描述）
        node_type: 节点类型
        ip_address: IP 地址（主接口）
        vendor: 设备厂商（仅 CPE/Gateway/Hub）
        model: 设备型号（仅 CPE/Gateway/Hub）
        interfaces: 接口列表（IP 地址列表）
        metadata: 附加元数据
    """
    id: str
    name: str
    node_type: NodeType
    ip_address: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    interfaces: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class Edge:
    """拓扑链路
    
    Attributes:
        id: 链路唯一标识
        source_id: 源节点 ID
        target_id: 目标节点 ID
        link_type: 链路类型
        source_interface: 源节点接口 IP
        target_interface: 目标节点接口 IP
        is_nat: 是否存在 NAT 转换
        nat_source: NAT 转换前地址（如果有）
        nat_destination: NAT 转换后地址（如果有）
        latency_ms: 链路延迟（毫秒，可选）
        packet_loss: 丢包率（0-1，可选）
        metadata: 附加元数据
    """
    id: str
    source_id: str
    target_id: str
    link_type: LinkType
    source_interface: Optional[str] = None
    target_interface: Optional[str] = None
    is_nat: bool = False
    nat_source: Optional[str] = None
    nat_destination: Optional[str] = None
    latency_ms: Optional[float] = None
    packet_loss: Optional[float] = None
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class NetworkTopology:
    """网络拓扑
    
    Attributes:
        nodes: 节点列表
        edges: 链路列表
        pc_node_id: PC 节点 ID（如果有）
        cpe_node_id: CPE 节点 ID（如果有）
        gateway_node_id: 网关节点 ID（如果有）
        hub_node_id: Hub 节点 ID（如果有）
        notes: 拓扑构建说明（如未画出 PC↔CPE 的原因），供报告展示
    """
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    pc_node_id: Optional[str] = None
    cpe_node_id: Optional[str] = None
    gateway_node_id: Optional[str] = None
    hub_node_id: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    
    def add_node(self, node: Node):
        """添加节点
        
        Args:
            node: 要添加的节点
        """
        self.nodes.append(node)
        
        # 自动记录特殊节点 ID
        if node.node_type == NodeType.PC:
            self.pc_node_id = node.id
        elif node.node_type == NodeType.CPE:
            self.cpe_node_id = node.id
        elif node.node_type == NodeType.GATEWAY:
            self.gateway_node_id = node.id
        elif node.node_type == NodeType.HUB:
            self.hub_node_id = node.id
    
    def add_edge(self, edge: Edge):
        """添加链路
        
        Args:
            edge: 要添加的链路
        """
        self.edges.append(edge)
    
    def get_node_by_id(self, node_id: str) -> Optional[Node]:
        """根据 ID 获取节点
        
        Args:
            node_id: 节点 ID
            
        Returns:
            节点对象，如果不存在返回 None
        """
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def get_edges_by_node(self, node_id: str) -> List[Edge]:
        """获取与指定节点相关的所有链路
        
        Args:
            node_id: 节点 ID
            
        Returns:
            链路列表
        """
        return [
            edge for edge in self.edges
            if edge.source_id == node_id or edge.target_id == node_id
        ]
    
    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 输出）
        
        Returns:
            拓扑字典表示
        """
        return {
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "type": node.node_type.value,
                    "ip_address": node.ip_address,
                    "vendor": node.vendor,
                    "model": node.model,
                    "interfaces": node.interfaces,
                    "metadata": node.metadata,
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "id": edge.id,
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "link_type": edge.link_type.value,
                    "source_interface": edge.source_interface,
                    "target_interface": edge.target_interface,
                    "is_nat": edge.is_nat,
                    "nat_source": edge.nat_source,
                    "nat_destination": edge.nat_destination,
                    "latency_ms": edge.latency_ms,
                    "packet_loss": edge.packet_loss,
                    "metadata": edge.metadata,
                }
                for edge in self.edges
            ],
            "pc_node_id": self.pc_node_id,
            "cpe_node_id": self.cpe_node_id,
            "gateway_node_id": self.gateway_node_id,
            "hub_node_id": self.hub_node_id,
            "topology_notes": list(self.notes),
        }
