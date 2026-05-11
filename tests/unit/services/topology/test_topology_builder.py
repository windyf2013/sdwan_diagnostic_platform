"""
拓扑构建器单元测试

测试 TopologyBuilder 的各项功能。
遵循 SDWAN_SPEC.md §2.5 拓扑构建规范
"""

import pytest

from sdwan_desktop.core.types.cpe_config import (
    CpeConfiguration,
    InterfaceInfo,
    RouteEntry,
    VpnTunnelInfo,
    NatRuleInfo,
)
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.topology.topology import NodeType, LinkType
from sdwan_desktop.services.topology.topology_builder import TopologyBuilder


@pytest.fixture
def sample_pc_data():
    """创建示例 PC 采集数据"""
    return {
        "hostname": "PC-001",
        "primary_ip": "192.168.1.100",
        "interfaces": ["192.168.1.100", "169.254.1.1"],
        "os": "Windows 10",
    }


@pytest.fixture
def sample_cpe_config():
    """创建示例 CPE 配置"""
    return CpeConfiguration(
        vendor="cisco_sdwan",
        model="VEDGE-1000",
        version="20.9.3",
        hostname="CPE-BRANCH-01",
        interfaces=[
            InterfaceInfo(name="GigabitEthernet0/0", ip_address="192.168.1.1", status="up"),
            InterfaceInfo(name="GigabitEthernet0/1", ip_address="10.0.0.1", status="up"),
            InterfaceInfo(name="Loopback0", ip_address="172.16.0.1", status="up"),
        ],
        routes=[
            RouteEntry(
                destination="0.0.0.0/0",
                gateway="192.168.1.254",
                interface="GigabitEthernet0/0",
                protocol="static",
                metric=1,
            ),
            RouteEntry(
                destination="10.0.0.0/8",
                gateway="10.0.0.254",
                interface="GigabitEthernet0/1",
                protocol="connected",
                metric=0,
            ),
        ],
        vpn_tunnels=[
            VpnTunnelInfo(
                remote_ip="203.0.113.1",
                local_color="biz-internet",
                remote_color="default",
                state="up",
                type="ipsec",
            ),
        ],
        nat_rules=[
            NatRuleInfo(
                protocol="tcp",
                inside_addr="192.168.1.100",
                outside_addr="203.0.113.100",
                nat_type="dynamic",
            ),
        ],
    )


@pytest.fixture
def successful_cpe_result(sample_cpe_config):
    """创建成功的 CPE 采集结果"""
    return CollectorResult(
        success=True,
        data={"cpe_configuration": sample_cpe_config},
        collected_items=["show version", "show interface", "show ip route"],
    )


@pytest.fixture
def failed_cpe_result():
    """创建失败的 CPE 采集结果"""
    return CollectorResult(
        success=False,
        error_message="Connection timeout",
    )


@pytest.fixture
def builder():
    """创建拓扑构建器实例"""
    return TopologyBuilder()


class TestTopologyBuilderBasic:
    """拓扑构建器基础测试"""
    
    def test_build_complete_topology(
        self,
        builder,
        sample_pc_data,
        successful_cpe_result,
    ):
        """测试完整拓扑构建"""
        topology = builder.build(sample_pc_data, successful_cpe_result)
        
        # 验证节点数量
        assert len(topology.nodes) == 4  # PC, CPE, GW, Hub
        
        # 验证链路数量
        assert len(topology.edges) >= 2  # PC→CPE, CPE→GW, CPE→Hub
        
        # 验证特殊节点 ID
        assert topology.pc_node_id == "pc-001"
        assert topology.cpe_node_id == "cpe-001"
        assert topology.gateway_node_id == "gw-001"
        assert topology.hub_node_id == "hub-001"
    
    def test_build_with_failed_cpe(
        self,
        builder,
        sample_pc_data,
        failed_cpe_result,
    ):
        """测试 CPE 采集失败时的拓扑构建"""
        topology = builder.build(sample_pc_data, failed_cpe_result)
        
        # 只应该有 PC 节点
        assert len(topology.nodes) == 1
        assert topology.pc_node_id == "pc-001"
        assert topology.cpe_node_id is None


class TestTopologyBuilderNodes:
    """节点构建测试"""
    
    def test_build_pc_node(self, builder, sample_pc_data):
        """测试 PC 节点构建"""
        node = builder._build_pc_node(sample_pc_data)
        
        assert node.id == "pc-001"
        assert node.name == "PC-001"
        assert node.node_type == NodeType.PC
        assert node.ip_address == "192.168.1.100"
        assert len(node.interfaces) == 2
        assert node.metadata["os"] == "Windows 10"
    
    def test_build_cpe_node(self, builder, sample_cpe_config):
        """测试 CPE 节点构建"""
        node = builder._build_cpe_node(sample_cpe_config)
        
        assert node.id == "cpe-001"
        assert node.name == "CPE-BRANCH-01"
        assert node.node_type == NodeType.CPE
        assert node.vendor == "cisco_sdwan"
        assert node.model == "VEDGE-1000"
        assert node.ip_address == "192.168.1.1"  # 第一个 WAN IP
        assert len(node.interfaces) == 3
    
    def test_build_gateway_node(self, builder, sample_cpe_config):
        """测试网关节点构建"""
        node = builder._build_gateway_node(sample_cpe_config)
        
        assert node is not None
        assert node.id == "gw-001"
        assert node.name == "Gateway (192.168.1.254)"
        assert node.node_type == NodeType.GATEWAY
        assert node.ip_address == "192.168.1.254"
    
    def test_build_gateway_node_no_route(self, builder):
        """测试无默认路由时跳过网关节点"""
        cpe_config = CpeConfiguration(vendor="cisco_sdwan", routes=[])
        node = builder._build_gateway_node(cpe_config)
        
        assert node is None
    
    def test_build_hub_node(self, builder, sample_cpe_config):
        """测试 Hub 节点构建"""
        node = builder._build_hub_node(sample_cpe_config)
        
        assert node is not None
        assert node.id == "hub-001"
        assert node.name == "Hub (203.0.113.1)"
        assert node.node_type == NodeType.HUB
        assert node.ip_address == "203.0.113.1"
    
    def test_build_hub_node_no_tunnel(self, builder):
        """测试无活跃隧道时跳过 Hub 节点"""
        cpe_config = CpeConfiguration(vendor="cisco_sdwan", vpn_tunnels=[])
        node = builder._build_hub_node(cpe_config)
        
        assert node is None


class TestTopologyBuilderEdges:
    """链路构建测试"""
    
    def test_build_pc_to_cpe_edge(self, builder, sample_pc_data, sample_cpe_config):
        """测试 PC → CPE 链路构建"""
        pc_node = builder._build_pc_node(sample_pc_data)
        cpe_node = builder._build_cpe_node(sample_cpe_config)
        
        edge = builder._build_pc_to_cpe_edge(pc_node, cpe_node, sample_pc_data)
        
        assert edge is not None
        assert edge.id == "link-pc-cpe"
        assert edge.source_id == "pc-001"
        assert edge.target_id == "cpe-001"
        assert edge.link_type == LinkType.PHYSICAL
        assert edge.source_interface == "192.168.1.100"
        assert edge.target_interface == "192.168.1.1"
    
    def test_build_cpe_to_gateway_edge(self, builder, sample_cpe_config):
        """测试 CPE → Gateway 链路构建"""
        cpe_node = builder._build_cpe_node(sample_cpe_config)
        gateway_node = builder._build_gateway_node(sample_cpe_config)
        
        edge = builder._build_cpe_to_gateway_edge(
            cpe_node, gateway_node, sample_cpe_config
        )
        
        assert edge is not None
        assert edge.id == "link-cpe-gw"
        assert edge.source_id == "cpe-001"
        assert edge.target_id == "gw-001"
        assert edge.link_type == LinkType.PHYSICAL
    
    def test_build_cpe_to_hub_edge(self, builder, sample_cpe_config):
        """测试 CPE → Hub 链路构建"""
        cpe_node = builder._build_cpe_node(sample_cpe_config)
        hub_node = builder._build_hub_node(sample_cpe_config)
        
        edge = builder._build_cpe_to_hub_edge(cpe_node, hub_node, sample_cpe_config)
        
        assert edge is not None
        assert edge.id == "link-cpe-hub"
        assert edge.source_id == "cpe-001"
        assert edge.target_id == "hub-001"
        assert edge.link_type == LinkType.TUNNEL


class TestTopologyBuilderNAT:
    """NAT 检测测试"""
    
    def test_detect_nat_traversal(self, builder, sample_cpe_config):
        """测试 NAT 转换检测"""
        from sdwan_desktop.services.topology.topology import NetworkTopology, Node, Edge, LinkType
        
        topology = NetworkTopology()
        
        # 添加 PC 和 CPE 节点
        pc_node = Node(id="pc-001", name="PC", node_type=NodeType.PC, ip_address="192.168.1.100")
        cpe_node = Node(id="cpe-001", name="CPE", node_type=NodeType.CPE, ip_address="192.168.1.1")
        topology.add_node(pc_node)
        topology.add_node(cpe_node)
        
        # 添加 PC → CPE 链路
        edge = Edge(
            id="link-pc-cpe",
            source_id="pc-001",
            target_id="cpe-001",
            link_type=LinkType.PHYSICAL,
            source_interface="192.168.1.100",
            target_interface="192.168.1.1",
        )
        topology.add_edge(edge)
        
        # 检测 NAT
        builder._detect_nat_traversal(topology, sample_cpe_config)
        
        # 验证 NAT 标记
        assert edge.is_nat is True
        assert edge.nat_source == "192.168.1.100"
        assert edge.nat_destination == "203.0.113.100"
    
    def test_detect_no_nat(self, builder):
        """测试无 NAT 规则时的检测"""
        from sdwan_desktop.services.topology.topology import NetworkTopology, Node, Edge, LinkType
        
        topology = NetworkTopology()
        cpe_config = CpeConfiguration(vendor="cisco_sdwan", nat_rules=[])
        
        # 添加节点和链路
        pc_node = Node(id="pc-001", name="PC", node_type=NodeType.PC, ip_address="192.168.1.100")
        cpe_node = Node(id="cpe-001", name="CPE", node_type=NodeType.CPE, ip_address="192.168.1.1")
        topology.add_node(pc_node)
        topology.add_node(cpe_node)
        
        edge = Edge(
            id="link-pc-cpe",
            source_id="pc-001",
            target_id="cpe-001",
            link_type=LinkType.PHYSICAL,
            source_interface="192.168.1.100",
            target_interface="192.168.1.1",
        )
        topology.add_edge(edge)
        
        # 检测 NAT
        builder._detect_nat_traversal(topology, cpe_config)
        
        # 验证没有 NAT 标记
        assert edge.is_nat is False
        assert edge.nat_source is None


class TestTopologyBuilderSerialization:
    """拓扑序列化测试"""
    
    def test_topology_to_dict(self, builder, sample_pc_data, successful_cpe_result):
        """测试拓扑序列化为字典"""
        topology = builder.build(sample_pc_data, successful_cpe_result)
        topo_dict = topology.to_dict()
        
        # 验证字典结构
        assert "nodes" in topo_dict
        assert "edges" in topo_dict
        assert "pc_node_id" in topo_dict
        assert "cpe_node_id" in topo_dict
        
        # 验证节点数量
        assert len(topo_dict["nodes"]) == 4
        
        # 验证第一个节点的结构
        first_node = topo_dict["nodes"][0]
        assert "id" in first_node
        assert "name" in first_node
        assert "type" in first_node
        assert "ip_address" in first_node
    
    def test_topology_json_serializable(self, builder, sample_pc_data, successful_cpe_result):
        """测试拓扑可 JSON 序列化"""
        import json
        
        topology = builder.build(sample_pc_data, successful_cpe_result)
        topo_dict = topology.to_dict()
        
        # 应该可以成功序列化为 JSON
        json_str = json.dumps(topo_dict)
        assert isinstance(json_str, str)
        assert len(json_str) > 0


class TestTopologyBuilderHelperMethods:
    """辅助方法测试"""
    
    def test_find_interface_for_route(self, builder, sample_cpe_config):
        """测试查找路由对应的接口"""
        route = sample_cpe_config.routes[0]  # 默认路由
        interface_ip = builder._find_interface_for_route(
            sample_cpe_config.interfaces, route
        )
        
        assert interface_ip == "192.168.1.1"
    
    def test_find_tunnel_local_interface(self, builder, sample_cpe_config):
        """测试查找隧道本地接口"""
        tunnel = sample_cpe_config.vpn_tunnels[0]
        local_ip = builder._find_tunnel_local_interface(
            sample_cpe_config.interfaces, tunnel
        )
        
        # 应该返回第一个 WAN 接口的 IP
        assert local_ip is not None
