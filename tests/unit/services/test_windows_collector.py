"""
WindowsCollector 单元测试

测试 WindowsCollector 的以下功能：
1. 正常采集流程（通过 mock ToolDispatcher）
2. 工具调用失败时的降级处理
3. dict 到结构化对象的转换（各子解析器）
4. 边界情况：空数据、部分数据、异常数据

遵循 SDWAN_SPEC_PATCHES.md PATCH-001 覆盖率门槛
遵循 SDWAN_SPEC_PATCHES.md PATCH-002 dict边界规则
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

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
from sdwan_desktop.services.collector.windows_collector import WindowsCollector


class TestWindowsCollector:
    """WindowsCollector 测试类"""

    def setup_method(self):
        """每个测试方法前初始化"""
        self.collector = WindowsCollector()
        self.ctx = FlowContext(
            flow_id="test-flow",
            flow_name="test",
            trace_id="test-trace-123",
        )

    # ==================== 正常采集流程 ====================

    @pytest.mark.asyncio
    async def test_collect_success(self):
        """测试正常采集流程 - 所有数据完整返回"""
        mock_dispatcher = AsyncMock()
        mock_dispatcher.dispatch.return_value = ToolResponse(
            success=True,
            data={
                "snapshot": {
                    "adapters": [
                        {
                            "name": "以太网",
                            "description": "Intel Ethernet Connection",
                            "mac_address": "00:11:22:33:44:55",
                            "adapter_type": "ethernet",
                            "status": "connected",
                            "is_connected": True,
                            "speed_mbps": 1000,
                            "ip_addresses": ["192.168.1.100"],
                            "ip_subnets": ["255.255.255.0"],
                            "default_gateway": "192.168.1.1",
                            "dhcp_enabled": True,
                            "dns_servers": ["8.8.8.8"],
                            "mtu": 1500,
                        }
                    ],
                    "ip_config": {
                        "ip_address": "192.168.1.100",
                        "subnet_mask": "255.255.255.0",
                        "default_gateway": "192.168.1.1",
                        "dhcp_enabled": True,
                        "dns_servers": ["8.8.8.8"],
                    },
                    "routes": [
                        {
                            "destination": "0.0.0.0",
                            "netmask": "0.0.0.0",
                            "gateway": "192.168.1.1",
                            "interface": "以太网",
                            "metric": 10,
                            "protocol": "static",
                        }
                    ],
                    "dns_config": {
                        "servers": ["8.8.8.8", "8.8.4.4"],
                        "suffix_search_order": ["local"],
                    },
                    "proxy_config": {
                        "enabled": False,
                        "server": None,
                        "bypass_list": [],
                    },
                    "firewall_status": {
                        "enabled": True,
                        "inbound_blocked": False,
                        "outbound_blocked": False,
                        "profiles": {"domain": True, "private": True, "public": True},
                        "icmp_blocked": False,
                        "rules_count": 50,
                    },
                    "arp_table": [
                        {
                            "ip_address": "192.168.1.1",
                            "mac_address": "aa:bb:cc:dd:ee:ff",
                            "interface": "以太网",
                            "type": "dynamic",
                        }
                    ],
                    "ipv6": {
                        "enabled": True,
                        "addresses": ["fe80::1"],
                        "default_gateway": None,
                        "dns_servers": [],
                        "is_preferred": False,
                    },
                    "hostname": "TEST-PC",
                    "os_version": "Windows 10 Pro",
                    "architecture": "x64",
                    "uptime_seconds": 3600,
                }
            },
            trace_id="test-trace-123",
        )

        collector = WindowsCollector(dispatcher=mock_dispatcher)
        snapshot = await collector.collect(self.ctx)

        # 验证整体结构
        assert isinstance(snapshot, SystemInfoSnapshot)
        assert snapshot.trace_id == "test-trace-123"

        # 验证网卡信息
        assert len(snapshot.adapters) == 1
        adapter = snapshot.adapters[0]
        assert adapter.name == "以太网"
        assert adapter.adapter_type == AdapterType.ETHERNET
        assert adapter.status == AdapterStatus.CONNECTED
        assert adapter.is_connected is True
        assert adapter.speed_mbps == 1000
        assert adapter.ip_addresses == ["192.168.1.100"]
        assert adapter.default_gateway == "192.168.1.1"

        # 验证IP配置
        assert snapshot.ip_config is not None
        assert snapshot.ip_config.ip_address == "192.168.1.100"
        assert snapshot.ip_config.default_gateway == "192.168.1.1"

        # 验证路由表
        assert len(snapshot.routes) == 1
        route = snapshot.routes[0]
        assert route.is_default_route is True
        assert route.gateway == "192.168.1.1"

        # 验证DNS配置
        assert snapshot.dns_config is not None
        assert "8.8.8.8" in snapshot.dns_config.servers

        # 验证代理配置
        assert snapshot.proxy_config is not None
        assert snapshot.proxy_config.enabled is False

        # 验证防火墙状态
        assert snapshot.firewall_status is not None
        assert snapshot.firewall_status.enabled is True
        assert snapshot.firewall_status.rules_count == 50

        # 验证ARP表
        assert len(snapshot.arp_table) == 1
        arp = snapshot.arp_table[0]
        assert arp.ip_address == "192.168.1.1"

        # 验证IPv6信息
        assert snapshot.ipv6 is not None
        assert snapshot.ipv6.enabled is True
        assert "fe80::1" in snapshot.ipv6.addresses

        # 验证系统信息
        assert snapshot.hostname == "TEST-PC"
        assert snapshot.os_version == "Windows 10 Pro"
        assert snapshot.architecture == "x64"
        assert snapshot.uptime_seconds == 3600

    # ==================== 工具调用失败降级 ====================

    @pytest.mark.asyncio
    async def test_collect_dispatcher_exception(self):
        """测试调度器抛出异常时的降级处理"""
        mock_dispatcher = AsyncMock()
        mock_dispatcher.dispatch.side_effect = Exception("调度器内部错误")

        collector = WindowsCollector(dispatcher=mock_dispatcher)
        snapshot = await collector.collect(self.ctx)

        assert isinstance(snapshot, SystemInfoSnapshot)
        assert snapshot.trace_id == "test-trace-123"
        # 降级后应返回空数据
        assert len(snapshot.adapters) == 0
        assert snapshot.ip_config is None
        assert snapshot.hostname is None

    @pytest.mark.asyncio
    async def test_collect_tool_failure(self):
        """测试工具返回失败状态时的降级处理"""
        mock_dispatcher = AsyncMock()
        mock_dispatcher.dispatch.return_value = ToolResponse(
            success=False,
            data=None,
            error_code="TOOL_EXECUTION_FAILED",
            error_message="工具执行失败",
            trace_id="test-trace-123",
        )

        collector = WindowsCollector(dispatcher=mock_dispatcher)
        snapshot = await collector.collect(self.ctx)

        assert isinstance(snapshot, SystemInfoSnapshot)
        assert snapshot.trace_id == "test-trace-123"
        # 降级后应返回空数据
        assert len(snapshot.adapters) == 0

    # ==================== 空数据和部分数据 ====================

    @pytest.mark.asyncio
    async def test_collect_empty_data(self):
        """测试工具返回空数据时的处理"""
        mock_dispatcher = AsyncMock()
        mock_dispatcher.dispatch.return_value = ToolResponse(
            success=True,
            data={"snapshot": {}},
            trace_id="test-trace-123",
        )

        collector = WindowsCollector(dispatcher=mock_dispatcher)
        snapshot = await collector.collect(self.ctx)

        assert isinstance(snapshot, SystemInfoSnapshot)
        assert len(snapshot.adapters) == 0
        assert snapshot.ip_config is None
        assert len(snapshot.routes) == 0
        assert snapshot.dns_config is None
        assert snapshot.proxy_config is None
        assert snapshot.firewall_status is None
        assert len(snapshot.arp_table) == 0
        assert snapshot.ipv6 is None
        assert snapshot.hostname is None

    @pytest.mark.asyncio
    async def test_collect_partial_data(self):
        """测试工具返回部分数据时的处理"""
        mock_dispatcher = AsyncMock()
        mock_dispatcher.dispatch.return_value = ToolResponse(
            success=True,
            data={
                "snapshot": {
                    "adapters": [],
                    "routes": [],
                    "arp_table": [],
                    "hostname": "PARTIAL-PC",
                    "os_version": "Windows 11",
                }
            },
            trace_id="test-trace-123",
        )

        collector = WindowsCollector(dispatcher=mock_dispatcher)
        snapshot = await collector.collect(self.ctx)

        assert snapshot.hostname == "PARTIAL-PC"
        assert snapshot.os_version == "Windows 11"
        assert len(snapshot.adapters) == 0
        assert snapshot.ip_config is None  # 未提供

    # ==================== 解析器单元测试 ====================

    def test_parse_adapter_list_full(self):
        """测试完整网卡数据解析"""
        raw_adapters = [
            {
                "name": "以太网",
                "description": "Intel Ethernet Connection",
                "mac_address": "00:11:22:33:44:55",
                "adapter_type": "ethernet",
                "status": "connected",
                "is_connected": True,
                "speed_mbps": 1000,
                "ip_addresses": ["192.168.1.100"],
                "ip_subnets": ["255.255.255.0"],
                "default_gateway": "192.168.1.1",
                "dhcp_enabled": True,
                "dns_servers": ["8.8.8.8"],
                "dns_suffix": "local",
                "mtu": 1500,
                "physical_address": "00-11-22-33-44-55",
                "manufacturer": "Intel",
                "driver_version": "12.0.0.1",
            }
        ]
        adapters = self.collector._parse_adapter_list(raw_adapters)
        assert len(adapters) == 1
        adapter = adapters[0]
        assert adapter.name == "以太网"
        assert adapter.adapter_type == AdapterType.ETHERNET
        assert adapter.status == AdapterStatus.CONNECTED
        assert adapter.speed_mbps == 1000
        assert adapter.manufacturer == "Intel"
        assert adapter.driver_version == "12.0.0.1"

    def test_parse_adapter_list_empty(self):
        """测试空网卡列表"""
        adapters = self.collector._parse_adapter_list([])
        assert len(adapters) == 0

    def test_parse_adapter_list_missing_fields(self):
        """测试网卡数据缺少字段"""
        raw_adapters = [{"name": "以太网"}]  # 只有name
        adapters = self.collector._parse_adapter_list(raw_adapters)
        assert len(adapters) == 1
        adapter = adapters[0]
        assert adapter.name == "以太网"
        # 缺少的字段应使用默认值
        assert adapter.mac_address == ""
        assert adapter.adapter_type == AdapterType.ETHERNET
        assert adapter.status == AdapterStatus.UNKNOWN
        assert adapter.is_connected is False

    def test_parse_adapter_list_invalid_data(self):
        """测试网卡数据异常（解析失败应跳过）"""
        raw_adapters = [
            {"name": "正常网卡", "mac_address": "00:11:22:33:44:55"},
            "invalid_data",  # 非dict数据
            {"name": "另一个网卡", "mac_address": "aa:bb:cc:dd:ee:ff"},
        ]
        adapters = self.collector._parse_adapter_list(raw_adapters)
        # 非dict数据应被跳过
        assert len(adapters) == 2

    def test_parse_ip_config_full(self):
        """测试完整IP配置解析"""
        raw = {
            "ip_address": "192.168.1.100",
            "subnet_mask": "255.255.255.0",
            "default_gateway": "192.168.1.1",
            "dhcp_enabled": True,
            "dns_servers": ["8.8.8.8"],
            "dns_suffix": "local",
            "dhcp_server": "192.168.1.1",
            "dhcp_lease_obtained": "2026-01-01 10:00:00",
            "dhcp_lease_expires": "2026-01-02 10:00:00",
            "wins_primary": None,
            "wins_secondary": None,
        }
        ip_config = self.collector._parse_ip_config(raw)
        assert ip_config is not None
        assert ip_config.ip_address == "192.168.1.100"
        assert ip_config.dhcp_enabled is True
        assert ip_config.dhcp_server == "192.168.1.1"

    def test_parse_ip_config_none(self):
        """测试IP配置为None"""
        ip_config = self.collector._parse_ip_config({})
        assert ip_config is not None
        assert ip_config.ip_address == ""

    def test_parse_route_list_full(self):
        """测试完整路由表解析"""
        raw_routes = [
            {
                "destination": "0.0.0.0",
                "netmask": "0.0.0.0",
                "gateway": "192.168.1.1",
                "interface": "以太网",
                "metric": 10,
                "protocol": "static",
                "persistent": True,
            }
        ]
        routes = self.collector._parse_route_list(raw_routes)
        assert len(routes) == 1
        route = routes[0]
        assert route.is_default_route is True
        assert route.persistent is True

    def test_parse_route_list_empty(self):
        """测试空路由表"""
        routes = self.collector._parse_route_list([])
        assert len(routes) == 0

    def test_parse_dns_config_full(self):
        """测试完整DNS配置解析"""
        raw = {
            "servers": ["8.8.8.8", "8.8.4.4"],
            "suffix_search_order": ["local", "company.local"],
            "primary_dns_suffix": "company.local",
            "connection_specific_suffix": "eth0.company.local",
            "registration_enabled": True,
            "dynamic_update_enabled": False,
        }
        dns = self.collector._parse_dns_config(raw)
        assert dns is not None
        assert len(dns.servers) == 2
        assert dns.primary_dns_suffix == "company.local"
        assert dns.dynamic_update_enabled is False

    def test_parse_dns_config_empty(self):
        """测试空DNS配置"""
        dns = self.collector._parse_dns_config({})
        assert dns is not None
        assert len(dns.servers) == 0

    def test_parse_proxy_config_enabled(self):
        """测试代理配置 - 已启用"""
        raw = {
            "enabled": True,
            "server": "proxy.company.com:8080",
            "bypass_list": ["*.local", "10.*"],
            "auto_config_url": "http://proxy.company.com/proxy.pac",
            "auto_detect_enabled": True,
        }
        proxy = self.collector._parse_proxy_config(raw)
        assert proxy is not None
        assert proxy.enabled is True
        assert proxy.server == "proxy.company.com:8080"
        assert len(proxy.bypass_list) == 2

    def test_parse_proxy_config_disabled(self):
        """测试代理配置 - 未启用"""
        proxy = self.collector._parse_proxy_config({})
        assert proxy is not None
        assert proxy.enabled is False
        assert proxy.server is None

    def test_parse_firewall_status_full(self):
        """测试完整防火墙状态解析"""
        raw = {
            "enabled": True,
            "inbound_blocked": False,
            "outbound_blocked": False,
            "profiles": {"domain": True, "private": True, "public": True},
            "icmp_blocked": False,
            "rules_count": 100,
        }
        fw = self.collector._parse_firewall_status(raw)
        assert fw is not None
        assert fw.enabled is True
        assert fw.rules_count == 100
        assert fw.profiles["domain"] is True

    def test_parse_firewall_status_empty(self):
        """测试空防火墙状态"""
        fw = self.collector._parse_firewall_status({})
        assert fw is not None
        assert fw.enabled is False
        assert fw.rules_count == 0

    def test_parse_arp_list_full(self):
        """测试完整ARP表解析"""
        raw_arp = [
            {
                "ip_address": "192.168.1.1",
                "mac_address": "aa:bb:cc:dd:ee:ff",
                "interface": "以太网",
                "type": "dynamic",
            }
        ]
        arp = self.collector._parse_arp_list(raw_arp)
        assert len(arp) == 1
        assert arp[0].ip_address == "192.168.1.1"
        assert arp[0].type == "dynamic"

    def test_parse_arp_list_empty(self):
        """测试空ARP表"""
        arp = self.collector._parse_arp_list([])
        assert len(arp) == 0

    def test_parse_connection_list_full(self):
        """测试完整活动连接解析"""
        raw_connections = [
            {
                "protocol": "tcp",
                "local_address": "192.168.1.100",
                "local_port": 54321,
                "remote_address": "10.0.0.1",
                "remote_port": 443,
                "state": "ESTABLISHED",
                "pid": 1234,
                "process_name": "chrome.exe",
            }
        ]
        connections = self.collector._parse_connection_list(raw_connections)
        assert len(connections) == 1
        conn = connections[0]
        assert conn.protocol == "tcp"
        assert conn.remote_port == 443
        assert conn.state == "ESTABLISHED"
        assert conn.process_name == "chrome.exe"

    def test_parse_connection_list_empty(self):
        """测试空活动连接列表"""
        connections = self.collector._parse_connection_list([])
        assert len(connections) == 0

    def test_parse_ipv6_info_enabled(self):
        """测试IPv6信息 - 已启用"""
        raw = {
            "enabled": True,
            "addresses": ["fe80::1", "2001:db8::1"],
            "default_gateway": "fe80::1",
            "dns_servers": ["2001:4860:4860::8888"],
            "is_preferred": False,
        }
        ipv6 = self.collector._parse_ipv6_info(raw)
        assert ipv6 is not None
        assert ipv6.enabled is True
        assert len(ipv6.addresses) == 2
        assert ipv6.default_gateway == "fe80::1"

    def test_parse_ipv6_info_disabled(self):
        """测试IPv6信息 - 未启用"""
        ipv6 = self.collector._parse_ipv6_info({})
        assert ipv6 is not None
        assert ipv6.enabled is False
        assert len(ipv6.addresses) == 0

    # ==================== 枚举解析器测试 ====================

    def test_parse_adapter_type(self):
        """测试网卡类型枚举解析"""
        assert self.collector._parse_adapter_type("ethernet") == AdapterType.ETHERNET
        assert self.collector._parse_adapter_type("wifi") == AdapterType.WIFI
        assert self.collector._parse_adapter_type("loopback") == AdapterType.LOOPBACK
        assert self.collector._parse_adapter_type("tunnel") == AdapterType.TUNNEL
        assert self.collector._parse_adapter_type("virtual") == AdapterType.VIRTUAL
        assert self.collector._parse_adapter_type("unknown") == AdapterType.OTHER
        assert self.collector._parse_adapter_type("") == AdapterType.OTHER

    def test_parse_adapter_status(self):
        """测试网卡状态枚举解析"""
        assert self.collector._parse_adapter_status("connected") == AdapterStatus.CONNECTED
        assert self.collector._parse_adapter_status("disconnected") == AdapterStatus.DISCONNECTED
        assert self.collector._parse_adapter_status("disabled") == AdapterStatus.DISABLED
        assert self.collector._parse_adapter_status("unknown") == AdapterStatus.UNKNOWN
        assert self.collector._parse_adapter_status("") == AdapterStatus.UNKNOWN

    # ==================== 边界情况 ====================

    @pytest.mark.asyncio
    async def test_collect_with_active_connections(self):
        """测试采集活动连接（当参数启用时）"""
        mock_dispatcher = AsyncMock()
        mock_dispatcher.dispatch.return_value = ToolResponse(
            success=True,
            data={
                "snapshot": {
                    "active_connections": [
                        {
                            "protocol": "tcp",
                            "local_address": "0.0.0.0",
                            "local_port": 135,
                            "remote_address": "0.0.0.0",
                            "remote_port": 0,
                            "state": "LISTEN",
                            "pid": 1234,
                            "process_name": "svchost.exe",
                        }
                    ],
                }
            },
            trace_id="test-trace-123",
        )

        collector = WindowsCollector(dispatcher=mock_dispatcher)
        snapshot = await collector.collect(self.ctx)

        assert len(snapshot.active_connections) == 1
        conn = snapshot.active_connections[0]
        assert conn.state == "LISTEN"
        assert conn.process_name == "svchost.exe"

    @pytest.mark.asyncio
    async def test_collect_no_active_connections_by_default(self):
        """测试默认不采集活动连接"""
        mock_dispatcher = AsyncMock()
        mock_dispatcher.dispatch.return_value = ToolResponse(
            success=True,
            data={"snapshot": {}},
            trace_id="test-trace-123",
        )

        collector = WindowsCollector(dispatcher=mock_dispatcher)
        snapshot = await collector.collect(self.ctx)

        # 默认不采集，但如果有数据则解析
        assert len(snapshot.active_connections) == 0

    def test_parse_adapter_list_case_insensitive_type(self):
        """测试网卡类型大小写不敏感"""
        raw_adapters = [
            {"name": "WiFi", "adapter_type": "WIFI", "status": "Connected"},
            {"name": "以太网", "adapter_type": "Ethernet", "status": "CONNECTED"},
        ]
        adapters = self.collector._parse_adapter_list(raw_adapters)
        assert len(adapters) == 2
        assert adapters[0].adapter_type == AdapterType.WIFI
        assert adapters[0].status == AdapterStatus.CONNECTED
        assert adapters[1].adapter_type == AdapterType.ETHERNET
        assert adapters[1].status == AdapterStatus.CONNECTED

    def test_parse_route_list_invalid_entries(self):
        """测试路由表中无效条目被跳过"""
        raw_routes = [
            {"destination": "10.0.0.0", "netmask": "255.0.0.0", "gateway": "10.0.0.1"},
            None,
            {},
            {"destination": "172.16.0.0", "netmask": "255.240.0.0", "gateway": "172.16.0.1"},
        ]
        routes = self.collector._parse_route_list(raw_routes)
        assert len(routes) == 3  # None 被跳过，空dict被解析为默认值

    def test_parse_arp_list_invalid_entries(self):
        """测试ARP表中无效条目被跳过"""
        raw_arp = [
            {"ip_address": "192.168.1.1", "mac_address": "aa:bb:cc:dd:ee:ff"},
            "invalid",
            123,
        ]
        arp = self.collector._parse_arp_list(raw_arp)
        assert len(arp) == 1  # 只有第一个有效

    # ==================== trace_id 贯穿测试 ====================

    @pytest.mark.asyncio
    async def test_trace_id_propagation(self):
        """测试 trace_id 贯穿全链路"""
        mock_dispatcher = AsyncMock()
        mock_dispatcher.dispatch.return_value = ToolResponse(
            success=True,
            data={"snapshot": {"hostname": "TEST-PC"}},
            trace_id="test-trace-123",
        )

        collector = WindowsCollector(dispatcher=mock_dispatcher)
        snapshot = await collector.collect(self.ctx)

        assert snapshot.trace_id == "test-trace-123"

        # 验证 dispatcher.dispatch 被正确调用
        call_args = mock_dispatcher.dispatch.call_args
        assert call_args is not None
        _, kwargs = call_args
        # dispatch 签名: dispatch(tool_name, request, ctx)
        assert kwargs["tool_name"] == "windows_system"
        assert kwargs["request"].trace_id == "test-trace-123"
        assert kwargs["ctx"].trace_id == "test-trace-123"
