"""
Cisco SD-WAN 解析器单元测试

测试 CiscoSdwanParser 的各项解析功能。
遵循 SDWAN_SPEC.md §2.4 工具系统规范
"""

import pytest
from sdwan_desktop.services.parser.vendor.cisco_sdwan import CiscoSdwanParser
from sdwan_desktop.services.parser.vendor import ConfigParserRegistry


@pytest.fixture
def parser():
    """创建 Cisco SD-WAN 解析器实例"""
    return CiscoSdwanParser()


class TestCiscoSdwanParser:
    """Cisco SD-WAN 解析器测试类"""
    
    def teardown_method(self):
        """测试清理"""
        ConfigParserRegistry.clear_all()

    # ==================== 厂商检测测试 ====================
    
    def test_detect_vendor_viptela(self, parser):
        """测试检测 Viptela 设备"""
        output = "Viptela VEDGE-1000 Software (vedge)"
        assert parser.detect_vendor(output) is True
    
    def test_detect_vendor_cedge(self, parser):
        """测试检测 cEdge 设备"""
        output = "Cisco IOS XE SDWAN Software (cedge)"
        assert parser.detect_vendor(output) is True
    
    def test_detect_vendor_vedge(self, parser):
        """测试检测 vEdge 设备"""
        output = "Cisco SD-WAN vEdge-2000"
        assert parser.detect_vendor(output) is True
    
    def test_detect_vendor_false(self, parser):
        """测试非 Cisco SD-WAN 设备"""
        output = "Huawei VRP Version 8.0"
        assert parser.detect_vendor(output) is False
    
    def test_detect_vendor_empty(self, parser):
        """测试空输出"""
        assert parser.detect_vendor("") is False
        assert parser.detect_vendor(None) is False
    
    # ==================== 版本解析测试 ====================
    
    def test_parse_version_standard(self, parser):
        """测试标准版本格式"""
        output = "Version 20.9.3"
        assert parser.parse_version(output) == "20.9.3"
    
    def test_parse_version_viptela_format(self, parser):
        """测试 Viptela 版本格式"""
        output = "viptela-20.9.3"
        assert parser.parse_version(output) == "20.9.3"
    
    def test_parse_version_vedge_format(self, parser):
        """测试 vEdge 版本格式"""
        output = "vedge-20.6.1"
        assert parser.parse_version(output) == "20.6.1"
    
    def test_parse_version_unknown(self, parser):
        """测试无法解析的版本"""
        output = "Some random text"
        assert parser.parse_version(output) == "unknown"
    
    def test_parse_version_empty(self, parser):
        """测试空输出"""
        assert parser.parse_version("") == "unknown"
    
    # ==================== 接口解析测试 ====================
    
    def test_parse_interfaces_single(self, parser):
        """测试解析单个接口"""
        output = """
Interface ge0/0
  Description: WAN Interface
  Status: up
  IP address: 192.168.1.1
  MAC: 00:1A:2B:3C:4D:5E
  MTU 1500
  Speed: 1 Gb/s
"""
        interfaces = parser.parse_interfaces(output)
        assert len(interfaces) == 1
        
        iface = interfaces[0]
        assert iface.name == "ge0/0"
        assert iface.description == "WAN Interface"
        assert iface.status == "up"
        assert iface.ip_address == "192.168.1.1"
        assert iface.mac_address == "00:1A:2B:3C:4D:5E"
        assert iface.mtu == 1500
        assert iface.speed_mbps == 1000
    
    def test_parse_interfaces_multiple(self, parser):
        """测试解析多个接口"""
        output = """
Interface ge0/0
  Status: up
  IP address: 192.168.1.1
  MTU 1500

Interface ge0/1
  Status: down
  IP address: 10.0.0.1
  MTU 1500
"""
        interfaces = parser.parse_interfaces(output)
        assert len(interfaces) == 2
        assert interfaces[0].name == "ge0/0"
        assert interfaces[1].name == "ge0/1"
    
    def test_parse_interfaces_status_variants(self, parser):
        """测试不同状态值的标准化"""
        output = """
Interface eth0
  Status: up/up
  
Interface eth1
  Status: administratively down
"""
        interfaces = parser.parse_interfaces(output)
        assert interfaces[0].status == "up"
        assert interfaces[1].status == "down"
    
    def test_parse_interfaces_empty(self, parser):
        """测试空输出"""
        interfaces = parser.parse_interfaces("")
        assert len(interfaces) == 0
    
    # ==================== 路由解析测试 ====================
    
    def test_parse_routes_connected(self, parser):
        """测试解析直连路由"""
        output = "C    10.0.0.0/24 is directly connected, ge0/0"
        routes = parser.parse_routes(output)
        
        assert len(routes) == 1
        route = routes[0]
        assert route.destination == "10.0.0.0/24"
        assert route.protocol == "connected"
        assert route.interface == "ge0/0"
        assert route.gateway is None
    
    def test_parse_routes_static(self, parser):
        """测试解析静态路由"""
        output = "S*   0.0.0.0/0 [1/0] via 192.168.1.1, ge0/1"
        routes = parser.parse_routes(output)
        
        assert len(routes) == 1
        route = routes[0]
        assert route.destination == "0.0.0.0/0"
        assert route.protocol == "static_default"
        assert route.gateway == "192.168.1.1"
        assert route.interface == "ge0/1"
        assert route.metric == 1
    
    def test_parse_routes_bgp(self, parser):
        """测试解析 BGP 路由"""
        output = "B    172.16.0.0/16 [200/0] via 10.1.1.1"
        routes = parser.parse_routes(output)
        
        assert len(routes) == 1
        route = routes[0]
        assert route.destination == "172.16.0.0/16"
        assert route.protocol == "bgp"
        assert route.gateway == "10.1.1.1"
        assert route.metric == 200
    
    def test_parse_routes_multiple(self, parser):
        """测试解析多条路由"""
        output = """
C    10.0.0.0/24 is directly connected, ge0/0
S*   0.0.0.0/0 [1/0] via 192.168.1.1, ge0/1
B    172.16.0.0/16 [200/0] via 10.1.1.1
"""
        routes = parser.parse_routes(output)
        assert len(routes) == 3
    
    def test_parse_routes_skip_header(self, parser):
        """测试跳过头部信息"""
        output = """
Codes: C - connected, S - static, B - BGP
Gateway of last resort is 192.168.1.1

C    10.0.0.0/24 is directly connected, ge0/0
"""
        routes = parser.parse_routes(output)
        assert len(routes) == 1
    
    def test_parse_routes_empty(self, parser):
        """测试空输出"""
        routes = parser.parse_routes("")
        assert len(routes) == 0
    
    # ==================== SD-WAN 策略解析测试 ====================
    
    def test_parse_sdwan_policies_single(self, parser):
        """测试解析单条 SD-WAN 策略"""
        output = """
Policy Internet-Access
  source-ip any
  destination-ip any
  app-list internet-apps
  sla-class gold
  preferred-path mpls
  backup-path internet
"""
        policies = parser.parse_sdwan_policies(output)
        
        assert len(policies) == 1
        policy = policies[0]
        assert policy.name == "Internet-Access"
        assert policy.source == "any"
        assert policy.destination == "any"
        assert policy.application == "internet-apps"
        assert policy.sla_class == "gold"
        assert policy.preferred_path == "mpls"
        assert policy.backup_path == "internet"
    
    def test_parse_sdwan_policies_multiple(self, parser):
        """测试解析多条 SD-WAN 策略"""
        output = """
Policy Policy-A
  source-ip 10.0.0.0/8
  destination-ip any

Policy Policy-B
  source-ip any
  destination-ip 172.16.0.0/12
"""
        policies = parser.parse_sdwan_policies(output)
        assert len(policies) == 2
    
    def test_parse_sdwan_policies_empty(self, parser):
        """测试空输出"""
        policies = parser.parse_sdwan_policies("")
        assert len(policies) == 0
    
    # ==================== VPN 隧道解析测试 ====================
    
    def test_parse_vpn_tunnels_up(self, parser):
        """测试解析 UP 状态的隧道"""
        output = "192.168.1.1  12345  blue  red  up"
        tunnels = parser.parse_vpn_tunnels(output)
        
        assert len(tunnels) == 1
        tunnel = tunnels[0]
        assert tunnel.remote_ip == "192.168.1.1"
        assert tunnel.local_color == "blue"
        assert tunnel.remote_color == "red"
        assert tunnel.state == "up"
        assert tunnel.type == "ipsec"
    
    def test_parse_vpn_tunnels_down(self, parser):
        """测试解析 DOWN 状态的隧道"""
        output = "10.0.0.1  67890  gold  silver  down"
        tunnels = parser.parse_vpn_tunnels(output)
        
        assert len(tunnels) == 1
        assert tunnels[0].state == "down"
    
    def test_parse_vpn_tunnels_multiple(self, parser):
        """测试解析多条隧道"""
        output = """
192.168.1.1  12345  blue  red  up
10.0.0.1     67890  gold  silver  down
172.16.0.1   11111  mpls  internet  up
"""
        tunnels = parser.parse_vpn_tunnels(output)
        assert len(tunnels) == 3
        assert tunnels[0].state == "up"
        assert tunnels[1].state == "down"
        assert tunnels[2].state == "up"
    
    def test_parse_vpn_tunnels_skip_header(self, parser):
        """测试跳过头部行"""
        output = """
ADDR         PORT   LOCAL-COLOR  REMOTE-COLOR  STATE
192.168.1.1  12345  blue         red           up
"""
        tunnels = parser.parse_vpn_tunnels(output)
        assert len(tunnels) == 1
    
    def test_parse_vpn_tunnels_empty(self, parser):
        """测试空输出"""
        tunnels = parser.parse_vpn_tunnels("")
        assert len(tunnels) == 0
    
    # ==================== NAT 规则解析测试 ====================
    
    def test_parse_nat_rules_dynamic(self, parser):
        """测试解析动态 NAT 规则"""
        output = "tcp  192.168.1.100:54321 203.0.113.10:54321 8.8.8.8:53 8.8.8.8:53"
        rules = parser.parse_nat_rules(output)
        
        assert len(rules) == 1
        rule = rules[0]
        assert rule.protocol == "tcp"
        assert rule.inside_addr == "192.168.1.100:54321"
        assert rule.outside_addr == "203.0.113.10:54321"
        assert rule.nat_type == "dynamic"
    
    def test_parse_nat_rules_multiple(self, parser):
        """测试解析多条 NAT 规则"""
        output = """
Pro  Inside global      Inside local       Outside local      Outside global
tcp  192.168.1.100:54321 203.0.113.10:54321 8.8.8.8:53         8.8.8.8:53
udp  192.168.1.101:12345 203.0.113.11:12345 8.8.4.4:53         8.8.4.4:53
"""
        rules = parser.parse_nat_rules(output)
        assert len(rules) == 2
    
    def test_parse_nat_rules_skip_header(self, parser):
        """测试跳过头部行"""
        output = """
Pro  Inside global      Inside local       Outside local      Outside global
---  ---                ---                ---                ---
tcp  192.168.1.100:54321 203.0.113.10:54321 8.8.8.8:53         8.8.8.8:53
"""
        rules = parser.parse_nat_rules(output)
        assert len(rules) == 1
    
    def test_parse_nat_rules_empty(self, parser):
        """测试空输出"""
        rules = parser.parse_nat_rules("")
        assert len(rules) == 0
    
    # ==================== 完整配置解析测试 ====================
    
    def test_parse_all_complete(self, parser):
        """测试完整配置解析"""
        raw_outputs = {
            "show version": "Viptela VEDGE-1000 Software (vedge)\nVersion 20.9.3",
            "show running-config": "hostname test-device",
            "show interface": """
Interface ge0/0
  Status: up
  IP address: 192.168.1.1
  MTU 1500
""",
            "show ip route": "C    10.0.0.0/24 is directly connected, ge0/0",
            "show sdwan policy": "",
            "show sdwan bfd sessions": "192.168.1.1  12345  blue  red  up",
            "show ip nat translations": "",
        }
        
        config = parser.parse_all(raw_outputs)
        
        assert config.vendor == "cisco_sdwan"
        assert config.model == "VEDGE-1000"
        assert config.version == "20.9.3"
        assert config.hostname == "test-device"
        assert len(config.interfaces) == 1
        assert len(config.routes) == 1
        assert len(config.vpn_tunnels) == 1
    
    def test_parse_all_minimal(self, parser):
        """测试最小配置解析（只有版本信息）"""
        raw_outputs = {
            "show version": "Version 20.9.3",
        }
        
        config = parser.parse_all(raw_outputs)
        
        assert config.vendor == "cisco_sdwan"
        assert config.version == "20.9.3"
        assert len(config.interfaces) == 0
        assert len(config.routes) == 0
    
    # ==================== 注册中心集成测试 ====================
    
    def test_register_parser(self):
        """测试注册解析器到注册中心"""
        ConfigParserRegistry.clear_all()
        
        parser = CiscoSdwanParser()
        ConfigParserRegistry.register(parser)
        
        assert "cisco_sdwan" in ConfigParserRegistry.list_vendors()
        
        retrieved = ConfigParserRegistry.get_parser("cisco_sdwan")
        assert retrieved is not None
        assert isinstance(retrieved, CiscoSdwanParser)
    
    def test_detect_and_parse(self):
        """测试自动检测并解析"""
        ConfigParserRegistry.clear_all()
        
        parser = CiscoSdwanParser()
        ConfigParserRegistry.register(parser)
        
        raw_outputs = {
            "show version": "Viptela VEDGE-1000 Software (vedge)\nVersion 20.9.3",
        }
        
        config = ConfigParserRegistry.detect_and_parse(raw_outputs)
        
        assert config.vendor == "cisco_sdwan"
        assert config.version == "20.9.3"
