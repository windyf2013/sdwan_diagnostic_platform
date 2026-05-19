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

    def test_cpe_unreachable_plus_business_probe(self, engine, mock_topology, mock_pc_data):
        """CPE 不可达时仍合并 ``business_probes`` 根因。"""
        result = CollectorResult(success=False, error_message="Connection timed out")
        probe = {
            "status": "partial",
            "data": {
                "business_probes": [
                    {
                        "domain": "app.example",
                        "port": 443,
                        "dns": {"status": "error", "data": None, "error": "nx"},
                        "tcp": [],
                    }
                ]
            },
        }
        causes = engine.analyze(mock_topology, result, mock_pc_data, targeted_probe=probe)
        ids = {c.cause_id for c in causes}
        assert "CPE-001" in ids
        assert "BIZ-DNS-001" in ids

    def test_business_tcp_from_targeted_probe_when_cpe_ok(self, engine, mock_topology, mock_pc_data):
        """正常 CPE 路径下从 ``targeted_probe`` 合并业务 TCP 根因。"""
        config = CpeConfiguration(
            vendor="cisco",
            vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="up")],
            sdwan_policies=[
                SdwanPolicy(name="p1", source="any", destination="any", application="any", sla_class="gold")
            ],
            nat_rules=[NatRuleInfo(protocol="tcp", inside_addr="192.168.1.0/24", outside_addr="1.1.1.1")],
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        probe = {
            "status": "ok",
            "data": {
                "business_probes": [
                    {
                        "domain": "svc.example",
                        "port": 443,
                        "dns": {
                            "status": "ok",
                            "data": {"resolved_ips": ["203.0.113.1"]},
                            "error": None,
                        },
                        "tcp": [
                            {
                                "host": "203.0.113.1",
                                "port": 443,
                                "status": "ok",
                                "data": {"port_open": False},
                            }
                        ],
                    }
                ]
            },
        }
        causes = engine.analyze(mock_topology, result, mock_pc_data, targeted_probe=probe)
        assert any(c.cause_id.startswith("BIZ-TCP") for c in causes)

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

    def test_link_protect_down_from_targeted_probe(self, engine, mock_topology, mock_pc_data):
        """拓扑后 ``show link-protect status`` 含 Down 时补充 RAISECOM-LINK-PROT-001。"""
        config = CpeConfiguration(
            vendor="raisecom",
            vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="up")],
            sdwan_policies=[
                SdwanPolicy(name="p1", source="any", destination="any", application="any", sla_class="gold")
            ],
            nat_rules=[NatRuleInfo(protocol="tcp", inside_addr="192.168.1.0/24", outside_addr="1.1.1.1")],
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        raw = "protect group vxlan1 :\n  current action status : down\n"
        probe = {"status": "ok", "data": {"raw_outputs": {"show link-protect status": raw}}}
        causes = engine.analyze(mock_topology, result, mock_pc_data, targeted_probe=probe)
        assert any(c.cause_id == "RAISECOM-LINK-PROT-001" for c in causes)

    def test_session_evidence_does_not_boost_nat_policy_when_no_session(
        self, engine, mock_topology, mock_pc_data
    ):
        config = CpeConfiguration(
            vendor="raisecom",
            vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="up")],
            sdwan_policies=[],
            nat_rules=[NatRuleInfo(protocol="tcp", inside_addr="172.16.0.0/16", outside_addr="1.1.1.1")],
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        probe = {
            "status": "ok",
            "data": {
                "biz_target_ips": ["69.171.235.22"],
                "raw_outputs": {"diagnose:nf_conntrack grep 69.171.235.22": ""},
                "business_probes": [
                    {
                        "domain": "www.tiktok.com",
                        "port": 443,
                        "dns": {"status": "ok", "data": {"resolved_ips": ["69.171.235.22"]}, "error": None},
                        "tcp": [{"host": "69.171.235.22", "port": 443, "status": "error", "error": "timeout"}],
                    }
                ],
            },
        }
        causes = engine.analyze(mock_topology, result, mock_pc_data, targeted_probe=probe)
        nat = next(c for c in causes if c.cause_id == "CPE-004")
        policy = next(c for c in causes if c.cause_id == "CPE-003")
        assert nat.confidence <= 0.66
        assert policy.confidence <= 0.66
        assert "不能" in nat.description

    def test_session_evidence_reduces_nat_policy_confidence_when_established(
        self, engine, mock_topology, mock_pc_data
    ):
        config = CpeConfiguration(
            vendor="raisecom",
            vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="up")],
            sdwan_policies=[],
            nat_rules=[NatRuleInfo(protocol="tcp", inside_addr="172.16.0.0/16", outside_addr="1.1.1.1")],
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        probe = {
            "status": "ok",
            "data": {
                "biz_target_ips": ["69.171.235.22"],
                "raw_outputs": {
                    "diagnose:nf_conntrack grep 69.171.235.22": (
                        "tcp 6 431 ESTABLISHED src=10.10.100.161 dst=69.171.235.22 sport=50124 dport=443 [ASSURED]"
                    )
                },
                "business_probes": [
                    {
                        "domain": "www.tiktok.com",
                        "port": 443,
                        "dns": {"status": "ok", "data": {"resolved_ips": ["69.171.235.22"]}, "error": None},
                        "tcp": [{"host": "69.171.235.22", "port": 443, "status": "error", "error": "timeout"}],
                    }
                ],
            },
        }
        causes = engine.analyze(mock_topology, result, mock_pc_data, targeted_probe=probe)
        nat = next(c for c in causes if c.cause_id == "CPE-004")
        policy = next(c for c in causes if c.cause_id == "CPE-003")
        assert nat.confidence <= 0.62
        assert policy.confidence <= 0.62
        assert "ESTABLISHED:1" in nat.description

    def test_reconcile_policy_severity_when_targeted_business_all_ok(
        self, engine, mock_topology, mock_pc_data
    ):
        """拓扑后业务探测已全部成功时，CPE-003 启发式降为 WARNING 并补充与观测一致说明。"""
        config = CpeConfiguration(
            vendor="cisco",
            vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="up")],
            sdwan_policies=[],
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        probe = {
            "status": "ok",
            "data": {
                "business_probes": [
                    {
                        "domain": "x.example",
                        "port": 443,
                        "dns": {"status": "ok", "data": {}, "error": None},
                        "tcp": [
                            {
                                "host": "8.8.8.8",
                                "port": 443,
                                "status": "ok",
                                "data": {"port_open": True},
                            }
                        ],
                    }
                ],
            },
        }
        causes = engine.analyze(mock_topology, result, mock_pc_data, targeted_probe=probe)
        policy = next(c for c in causes if c.cause_id == "CPE-003")
        assert policy.severity == Severity.WARNING
        assert "与本机/拓扑后探测一致" in policy.description

    def test_session_time_wait_uses_closing_residual_branch(
        self, engine, mock_topology, mock_pc_data
    ):
        """TIME_WAIT 为主时不应走「仅 SYN」黑洞话术。"""
        config = CpeConfiguration(
            vendor="raisecom",
            vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="up")],
            sdwan_policies=[],
            nat_rules=[NatRuleInfo(protocol="tcp", inside_addr="172.16.0.0/16", outside_addr="1.1.1.1")],
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        probe = {
            "status": "ok",
            "data": {
                "biz_target_ips": ["8.8.8.8"],
                "raw_outputs": {
                    "diagnose:nf_conntrack grep 8.8.8.8": (
                        "tcp 6 10 TIME_WAIT src=192.168.1.100 dst=8.8.8.8 sport=444 dport=443"
                    )
                },
                "business_probes": [
                    {
                        "domain": "x.example",
                        "port": 443,
                        "dns": {"status": "ok", "data": {}, "error": None},
                        "tcp": [
                            {
                                "host": "8.8.8.8",
                                "port": 443,
                                "status": "ok",
                                "data": {"port_open": True},
                            }
                        ],
                    }
                ],
            },
        }
        causes = engine.analyze(mock_topology, result, mock_pc_data, targeted_probe=probe)
        policy = next(c for c in causes if c.cause_id == "CPE-003")
        assert "收尾态" in policy.description
        assert "上游/远端不响应" not in policy.description

    def test_tunnel_syn_only_downgrades_cpe003_and_cpe004(self, engine, mock_topology, mock_pc_data):
        """隧道 peer 全通且 conntrack 仅 SYN 时，不应再以 ERROR 断言策略/NAT 与隧道转发矛盾。"""
        config = CpeConfiguration(
            vendor="raisecom",
            vpn_tunnels=[VpnTunnelInfo(remote_ip="10.0.0.2", state="up")],
            sdwan_policies=[],
            nat_rules=[NatRuleInfo(protocol="tcp", inside_addr="172.16.0.0/16", outside_addr="1.1.1.1")],
        )
        result = CollectorResult(success=True, data={"cpe_configuration": config})
        ping_ok = "2 packets transmitted, 2 received, 0% packet loss\n"
        probe = {
            "status": "ok",
            "data": {
                "biz_target_ips": ["69.171.235.22"],
                "raw_outputs": {
                    "diagnose:ping tunnel_peer 10.0.0.2": ping_ok,
                    "diagnose:nf_conntrack grep 69.171.235.22": (
                        "tcp 6 120 SYN_SENT src=192.168.1.100 dst=69.171.235.22 sport=50124 dport=443"
                    ),
                },
                "business_probes": [
                    {
                        "domain": "www.tiktok.com",
                        "port": 443,
                        "dns": {"status": "ok", "data": {"resolved_ips": ["69.171.235.22"]}, "error": None},
                        "tcp": [
                            {
                                "host": "69.171.235.22",
                                "port": 443,
                                "status": "error",
                                "error": "timeout",
                            }
                        ],
                    }
                ],
            },
        }
        causes = engine.analyze(mock_topology, result, mock_pc_data, targeted_probe=probe)
        p3 = next(c for c in causes if c.cause_id == "CPE-003")
        p4 = next(c for c in causes if c.cause_id == "CPE-004")
        assert p3.severity == Severity.WARNING
        assert p4.severity == Severity.WARNING
        assert "策略路由未生效" not in p3.title
        assert "NAT 不匹配" not in p4.title
        assert "隧道/会话观测对齐" in p3.description
        assert "隧道/会话观测对齐" in p4.description
