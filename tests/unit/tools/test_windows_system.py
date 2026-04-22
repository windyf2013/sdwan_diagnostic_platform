"""Windows系统工具测试"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.implementations.system.windows import WindowsSystemTool


class TestWindowsSystemTool:
    """WindowsSystemTool测试类"""

    def setup_method(self):
        """测试初始化"""
        self.tool = WindowsSystemTool()
        self.ctx = FlowContext(
            flow_id="test-flow",
            flow_name="test",
            trace_id="test-trace-123"
        )

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """测试执行成功"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": False,
                "collect_routes": False,
                "collect_dns": False,
                "collect_proxy": False,
                "collect_firewall": False,
                "collect_arp": False,
                "collect_connections": False,
                "collect_ipv6": False,
            }
        )

        response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data
        assert response.trace_id == "test-trace-123"

    @pytest.mark.asyncio
    async def test_execute_with_adapters(self):
        """测试采集网卡信息"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": True,
                "collect_routes": False,
                "collect_dns": False,
                "collect_proxy": False,
                "collect_firewall": False,
                "collect_arp": False,
                "collect_connections": False,
                "collect_ipv6": False,
            }
        )

        with patch.object(self.tool, '_get_network_adapters', new_callable=AsyncMock) as mock_adapters:
            mock_adapters.return_value = []
            response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_execute_with_routes(self):
        """测试采集路由表"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": False,
                "collect_routes": True,
                "collect_dns": False,
                "collect_proxy": False,
                "collect_firewall": False,
                "collect_arp": False,
                "collect_connections": False,
                "collect_ipv6": False,
            }
        )

        with patch.object(self.tool, '_get_routing_table', new_callable=AsyncMock) as mock_routes:
            mock_routes.return_value = []
            response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_execute_with_dns(self):
        """测试采集DNS配置"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": False,
                "collect_routes": False,
                "collect_dns": True,
                "collect_proxy": False,
                "collect_firewall": False,
                "collect_arp": False,
                "collect_connections": False,
                "collect_ipv6": False,
            }
        )

        with patch.object(self.tool, '_get_dns_config', new_callable=AsyncMock) as mock_dns:
            mock_dns.return_value = MagicMock(servers=["8.8.8.8"])
            response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_execute_with_proxy(self):
        """测试采集代理配置"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": False,
                "collect_routes": False,
                "collect_dns": False,
                "collect_proxy": True,
                "collect_firewall": False,
                "collect_arp": False,
                "collect_connections": False,
                "collect_ipv6": False,
            }
        )

        with patch.object(self.tool, '_get_proxy_config', new_callable=AsyncMock) as mock_proxy:
            mock_proxy.return_value = MagicMock(enabled=False, server="", bypass_list=[])
            response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_execute_with_firewall(self):
        """测试采集防火墙状态"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": False,
                "collect_routes": False,
                "collect_dns": False,
                "collect_proxy": False,
                "collect_firewall": True,
                "collect_arp": False,
                "collect_connections": False,
                "collect_ipv6": False,
            }
        )

        with patch.object(self.tool, '_get_firewall_status', new_callable=AsyncMock) as mock_fw:
            mock_fw.return_value = MagicMock(enabled=False, profiles={})
            response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_execute_with_arp(self):
        """测试采集ARP表"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": False,
                "collect_routes": False,
                "collect_dns": False,
                "collect_proxy": False,
                "collect_firewall": False,
                "collect_arp": True,
                "collect_connections": False,
                "collect_ipv6": False,
            }
        )

        with patch.object(self.tool, '_get_arp_table', new_callable=AsyncMock) as mock_arp:
            mock_arp.return_value = []
            response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_execute_with_connections(self):
        """测试采集活动连接"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": False,
                "collect_routes": False,
                "collect_dns": False,
                "collect_proxy": False,
                "collect_firewall": False,
                "collect_arp": False,
                "collect_connections": True,
                "collect_ipv6": False,
            }
        )

        with patch.object(self.tool, '_get_active_connections', new_callable=AsyncMock) as mock_conn:
            mock_conn.return_value = []
            response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_execute_with_ipv6(self):
        """测试采集IPv6信息"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": False,
                "collect_routes": False,
                "collect_dns": False,
                "collect_proxy": False,
                "collect_firewall": False,
                "collect_arp": False,
                "collect_connections": False,
                "collect_ipv6": True,
            }
        )

        with patch.object(self.tool, '_get_ipv6_info', new_callable=AsyncMock) as mock_ipv6:
            mock_ipv6.return_value = MagicMock(enabled=False, addresses=[], is_preferred=False)
            response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_execute_all_collections(self):
        """测试采集所有信息"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": True,
                "collect_routes": True,
                "collect_dns": True,
                "collect_proxy": True,
                "collect_firewall": True,
                "collect_arp": True,
                "collect_connections": True,
                "collect_ipv6": True,
            }
        )

        with patch.object(self.tool, '_get_network_adapters', new_callable=AsyncMock) as mock_adapters:
            mock_adapters.return_value = []
            with patch.object(self.tool, '_get_routing_table', new_callable=AsyncMock) as mock_routes:
                mock_routes.return_value = []
                with patch.object(self.tool, '_get_dns_config', new_callable=AsyncMock) as mock_dns:
                    mock_dns.return_value = MagicMock(servers=[])
                    with patch.object(self.tool, '_get_proxy_config', new_callable=AsyncMock) as mock_proxy:
                        mock_proxy.return_value = MagicMock(enabled=False, server="", bypass_list=[])
                        with patch.object(self.tool, '_get_firewall_status', new_callable=AsyncMock) as mock_fw:
                            mock_fw.return_value = MagicMock(enabled=False, profiles={})
                            with patch.object(self.tool, '_get_arp_table', new_callable=AsyncMock) as mock_arp:
                                mock_arp.return_value = []
                                with patch.object(self.tool, '_get_active_connections', new_callable=AsyncMock) as mock_conn:
                                    mock_conn.return_value = []
                                    with patch.object(self.tool, '_get_ipv6_info', new_callable=AsyncMock) as mock_ipv6:
                                        mock_ipv6.return_value = MagicMock(enabled=False, addresses=[], is_preferred=False)
                                        response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_execute_partial_failure(self):
        """测试部分采集失败"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={
                "collect_adapters": True,
                "collect_routes": False,
                "collect_dns": False,
                "collect_proxy": False,
                "collect_firewall": False,
                "collect_arp": False,
                "collect_connections": False,
                "collect_ipv6": False,
            }
        )

        with patch.object(self.tool, '_get_network_adapters', new_callable=AsyncMock) as mock_adapters:
            mock_adapters.side_effect = Exception("WMI不可用")
            response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_execute_with_default_params(self):
        """测试默认参数"""
        request = ToolRequest(
            tool_name="windows_system",
            parameters={}
        )

        with patch.object(self.tool, '_get_network_adapters', new_callable=AsyncMock) as mock_adapters:
            mock_adapters.return_value = []
            with patch.object(self.tool, '_get_routing_table', new_callable=AsyncMock) as mock_routes:
                mock_routes.return_value = []
                with patch.object(self.tool, '_get_dns_config', new_callable=AsyncMock) as mock_dns:
                    mock_dns.return_value = MagicMock(servers=[])
                    with patch.object(self.tool, '_get_proxy_config', new_callable=AsyncMock) as mock_proxy:
                        mock_proxy.return_value = MagicMock(enabled=False, server="", bypass_list=[])
                        with patch.object(self.tool, '_get_firewall_status', new_callable=AsyncMock) as mock_fw:
                            mock_fw.return_value = MagicMock(enabled=False, profiles={})
                            with patch.object(self.tool, '_get_arp_table', new_callable=AsyncMock) as mock_arp:
                                mock_arp.return_value = []
                                with patch.object(self.tool, '_get_ipv6_info', new_callable=AsyncMock) as mock_ipv6:
                                    mock_ipv6.return_value = MagicMock(enabled=False, addresses=[], is_preferred=False)
                                    response = await self.tool.execute(request, self.ctx)

        assert response.success is True
        assert "snapshot" in response.data

    @pytest.mark.asyncio
    async def test_detect_adapter_type(self):
        """测试网卡类型检测"""
        assert self.tool._detect_adapter_type("Intel(R) Ethernet Connection") == "ethernet"
        assert self.tool._detect_adapter_type("Wireless-AC 9560") == "wifi"
        assert self.tool._detect_adapter_type("Loopback Pseudo-Interface") == "loopback"
        assert self.tool._detect_adapter_type("Tunnel adapter isatap") == "tunnel"
        assert self.tool._detect_adapter_type("VMware Virtual Ethernet Adapter") == "virtual"
        assert self.tool._detect_adapter_type("VirtualBox Host-Only Ethernet Adapter") == "virtual"
