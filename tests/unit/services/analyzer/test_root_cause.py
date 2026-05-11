"""
根因分析引擎单元测试

覆盖 CPE-001, CPE-002, CPE-003, CPE-004, OVERLAY-001 等故障场景。
"""

import pytest
from unittest.mock import MagicMock

from sdwan_desktop.core.types.cpe_config import (
    CpeConfiguration, VpnTunnelInfo, NatRuleInfo, SdwanPolicy, RouteEntry
)
from sdwan_desktop.core.types.diagnosis import Severity
from sdwan_desktop.services.analyzer.root_cause import RootCauseEngine
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.topology.topology import NetworkTopology, Node, NodeType


@pytest.fixture
def engine():
    return RootCauseEngine()


@pytest.fixture
def mock_topology():
    topology = NetworkTopology()
    topology.add_node(Node(id="pc-001", name="PC", node_type=NodeType.PC, ip_address="192.168.1.100"))
    topology.add_node(Node(id="cpe-001", name="CPE", node_type=NodeType.CPE, ip_address="10.0.0.1"))
    topology.pc_node_id = "pc-001"
    topology.cpe_node_id = "cpe-001"
    return topology


@pytest.fixture
def mock_pc_data():
    return {"primary_ip": "192.168.1.100"}


class TestRootCauseEngine:

    def test_cpe_unreachable(self, engine, mock_topology, mock_pc_data):
        """测试 CPE-001: CPE 不可达"""
        result = CollectorResult(success=False, error_message="Connection timed out")
        causes = engine.analyze(mock_topology, result, mock_pc_data)
        
        assert len(causes) == 1
        assert causes[0].cause_id == "CPE-001"
        assert causes[0].severity == Severity.CRITICAL

    def test_tunnel_down(self, engine, mock_topology, mock_pc_data):
        """测试 CPE-002: 隧道 Down"""
        config = CpeConfiguration(
            vendor="cisco", 
            vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="down")]
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        
        causes = engine.analyze(mock_topology, result, mock_pc_data)
        
        cpe_002 = [c for c in causes if c.cause_id == "CPE-002"]
        assert len(cpe_002) == 1

    def test_policy_routing_missing(self, engine, mock_topology, mock_pc_data):
        """测试 CPE-003: 策略路由未生效"""
        config = CpeConfiguration(
            vendor="cisco",
            vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="up")],
            sdwan_policies=[]  # 无策略
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        
        causes = engine.analyze(mock_topology, result, mock_pc_data)
        
        cpe_003 = [c for c in causes if c.cause_id == "CPE-003"]
        assert len(cpe_003) == 1

    def test_nat_mismatch(self, engine, mock_topology, mock_pc_data):
        """测试 CPE-004: NAT 不匹配"""
        config = CpeConfiguration(
            vendor="cisco",
            vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="up")],
            nat_rules=[NatRuleInfo(protocol="tcp", inside_addr="172.16.0.0/16", outside_addr="1.1.1.1")]
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        
        causes = engine.analyze(mock_topology, result, mock_pc_data)
        
        cpe_004 = [c for c in causes if c.cause_id == "CPE-004"]
        assert len(cpe_004) == 1

    def test_no_issues(self, engine, mock_topology, mock_pc_data):
        """测试无问题的情况"""
        config = CpeConfiguration(
            vendor="cisco",
            vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="up")],
            sdwan_policies=[SdwanPolicy(name="p1", source="any", destination="any", application="any", sla_class="gold")],
            nat_rules=[NatRuleInfo(protocol="tcp", inside_addr="192.168.1.0/24", outside_addr="1.1.1.1")]
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        
        causes = engine.analyze(mock_topology, result, mock_pc_data)
        
        # 应该没有识别出任何根因
        assert len(causes) == 0
