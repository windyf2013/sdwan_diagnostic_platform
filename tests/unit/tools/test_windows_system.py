"""WindowsSystemTool单元测试"""

from unittest.mock import MagicMock, patch
import pytest
import subprocess

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
    async def test_windows_system_collect_all(self):
        """测试完整系统信息采集"""
        request = ToolRequest(parameters={})
        
        # Mock所有外部依赖
        with patch('wmi.WMI') as mock_wmi_class, \
             patch('subprocess.run') as mock_subprocess, \
             patch('winreg.OpenKey') as mock_reg_open, \
             patch('winreg.QueryValueEx') as mock_reg_query:
            
            # Mock WMI网络适配器
            mock_wmi = MagicMock()
            mock_wmi_class.return_value = mock_wmi
            
            mock_nic = MagicMock()
            mock_nic.Description = "Intel(R) Ethernet Connection (7) I219-V"
            mock_nic.MACAddress = "00:11:22:33:44:55"
            mock_nic.IPAddress = ["192.168.1.100", "fe80::1234"]
            mock_nic.IPSubnet = ["255.255.255.0", "64"]
            mock_nic.DefaultIPGateway = ["192.168.1.1"]
            mock_nic.DHCPEnabled = True
            mock_nic.DNSServerSearchOrder = ["8.8.8.8", "8.8.4.4"]
            mock_nic.DNSDomainSuffixSearchOrder = ["local"]
            
            mock_wmi.Win32_NetworkAdapterConfiguration.return_value = [mock_nic]
            
            # Mock route print输出
            mock_route_result = MagicMock()
            mock_route_result.stdout = """
===========================================================================
接口列表
  1...........................Software Loopback Interface 1
  2...00 11 22 33 44 55 ......Intel(R) Ethernet Connection (7) I219-V
===========================================================================
IPv4 路由表
===========================================================================
活动路由:
网络目标        网络掩码          网关       接口   跃点数
          0.0.0.0          0.0.0.0      192.168.1.1    192.168.1.100     25
        127.0.0.0        255.0.0.0        在链路上         127.0.0.1    331
        127.0.0.1  255.255.255.255        在链路上         127.0.0.1    331
   192.168.1.0    255.255.255.0        在链路上     192.168.1.100    281
   192.168.1.100  255.255.255.255        在链路上     192.168.1.100    281
   192.168.1.255  255.255.255.255        在链路上     192.168.1.100    281
===========================================================================
"""
            mock_route_result.returncode = 0
            
            # Mock nslookup输出
            mock_nslookup_result = MagicMock()
            mock_nslookup_result.stdout = """
服务器:  dns.google
Address:  8.8.8.8

DNS request timed out.
    timeout was 2 seconds.
"""
            mock_nslookup_result.returncode = 0
            
            # Mock netsh防火墙输出
            mock_firewall_result = MagicMock()
            mock_firewall_result.stdout = """
域配置文件设置:
状态                                  启用

专用配置文件设置:
状态                                  启用

公用配置文件设置:
状态                                  启用
"""
            mock_firewall_result.returncode = 0
            
            # Mock netstat输出
            mock_netstat_result = MagicMock()
            mock_netstat_result.stdout = """
活动连接

  协议  本地地址          外部地址        状态
  TCP    192.168.1.100:49668  52.114.128.44:443    ESTABLISHED
  TCP    192.168.1.100:49669  13.107.42.14:443     ESTABLISHED
  TCP    192.168.1.100:49670  20.190.159.97:443    TIME_WAIT
"""
            mock_netstat_result.returncode = 0
            
            # Mock arp输出
            mock_arp_result = MagicMock()
            mock_arp_result.stdout = """
接口: 192.168.1.100 --- 0x2
  Internet 地址         物理地址              类型
  192.168.1.1           00-11-22-33-44-66     动态
  192.168.1.255         ff-ff-ff-ff-ff-ff     静态
  224.0.0.22            01-00-5e-00-00-16     静态
"""
            mock_arp_result.returncode = 0
            
            # 设置subprocess.run的返回值
            mock_subprocess.side_effect = [
                mock_route_result,    # route print
                mock_nslookup_result, # nslookup
                mock_firewall_result, # netsh advfirewall
                mock_netstat_result,  # netstat -an
                mock_arp_result       # arp -a
            ]
            
            # Mock注册表查询
            mock_reg_query.side_effect = [
                (1, 1),      # ProxyEnable = 1
                ("proxy.example.com:8080", 1),  # ProxyServer
                ("<local>", 1)  # ProxyOverride
            ]
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            data = response.data
            
            # 验证网络适配器信息
            assert len(data["network_adapters"]) == 1
            adapter = data["network_adapters"][0]
            assert adapter["description"] == "Intel(R) Ethernet Connection (7) I219-V"
            assert adapter["mac_address"] == "00:11:22:33:44:55"
            assert adapter["ip_addresses"] == ["192.168.1.100", "fe80::1234"]
            assert adapter["default_gateway"] == ["192.168.1.1"]
            assert adapter["dhcp_enabled"] is True
            
            # 验证路由表
            assert len(data["routing_table"]) > 0
            assert any(route["destination"] == "0.0.0.0" for route in data["routing_table"])
            
            # 验证DNS配置
            assert "default_servers" in data["dns_config"]
            
            # 验证代理配置
            assert data["proxy_config"]["proxy_enable"] is True
            assert data["proxy_config"]["proxy_server"] == "proxy.example.com:8080"
            
            # 验证防火墙状态
            assert "raw_output" in data["firewall_status"]
            
            # 验证活动连接
            assert len(data["active_connections"]) > 0
    
    @pytest.mark.asyncio
    async def test_windows_system_wmi_fallback(self):
        """测试WMI不可用时的降级方案"""
        request = ToolRequest(parameters={})
        
        with patch('wmi.WMI') as mock_wmi_class, \
             patch('subprocess.run') as mock_subprocess:
            
            # Mock WMI异常
            mock_wmi_class.side_effect = Exception("WMI not available")
            
            # Mock ipconfig输出作为备选
            mock_ipconfig_result = MagicMock()
            mock_ipconfig_result.stdout = """
Windows IP 配置

以太网适配器 以太网:

   连接特定的 DNS 后缀 . . . . . . . : local
   描述. . . . . . . . . . . . . . . : Intel(R) Ethernet Connection (7) I219-V
   物理地址. . . . . . . . . . . . . : 00-11-22-33-44-55
   DHCP 已启用 . . . . . . . . . . . : 是
   自动配置已启用. . . . . . . . . . : 是
   本地链接 IPv6 地址. . . . . . . . : fe80::1234%2(首选)
   IPv4 地址 . . . . . . . . . . . . : 192.168.1.100(首选)
   子网掩码  . . . . . . . . . . . . : 255.255.255.0
   默认网关. . . . . . . . . . . . . : 192.168.1.1
   DHCP 服务器 . . . . . . . . . . . : 192.168.1.1
   DNS 服务器  . . . . . . . . . . . : 8.8.8.8
                                       8.8.4.4
"""
            mock_ipconfig_result.returncode = 0
            
            # Mock其他命令输出
            mock_route_result = MagicMock()
            mock_route_result.stdout = "路由表输出"
            mock_route_result.returncode = 0
            
            mock_subprocess.side_effect = [
                mock_ipconfig_result,  # ipconfig /all
                mock_route_result,     # route print
                MagicMock(),           # nslookup
                MagicMock(),           # netsh
                MagicMock(),           # netstat
                MagicMock()            # arp
            ]
            
            response = await self.tool.execute(request, self.ctx)
            
            # 即使WMI失败，工具也应该成功返回
            assert response.success is True
            assert "network_adapters" in response.data
    
    @pytest.mark.asyncio
    async def test_windows_system_partial_failure(self):
        """测试部分采集失败不影响整体"""
        request = ToolRequest(parameters={})
        
        with patch('wmi.WMI') as mock_wmi_class, \
             patch('subprocess.run') as mock_subprocess, \
             patch('winreg.OpenKey') as mock_reg_open:
            
            # Mock WMI成功
            mock_wmi = MagicMock()
            mock_wmi_class.return_value = mock_wmi
            mock_wmi.Win32_NetworkAdapterConfiguration.return_value = []
            
            # Mock route命令失败
            mock_route_result = MagicMock()
            mock_route_result.stdout = ""
            mock_route_result.returncode = 1
            mock_route_result.stderr = "route命令失败"
            
            # Mock注册表访问失败
            mock_reg_open.side_effect = Exception("注册表访问被拒绝")
            
            # 设置subprocess.run返回值
            mock_subprocess.return_value = mock_route_result
            
            response = await self.tool.execute(request, self.ctx)
            
            # 即使部分采集失败，工具也应该成功返回
            assert response.success is True
            # 网络适配器列表应该为空
            assert response.data["network_adapters"] == []
            # 路由表应该为空或包含错误信息
            assert "routing_table" in response.data
    
    @pytest.mark.asyncio
    async def test_windows_system_english_locale(self):
        """测试英文系统环境"""
        request = ToolRequest(parameters={})
        
        with patch('wmi.WMI') as mock_wmi_class, \
             patch('subprocess.run') as mock_subprocess:
            
            # Mock WMI
            mock_wmi = MagicMock()
            mock_wmi_class.return_value = mock_wmi
            mock_wmi.Win32_NetworkAdapterConfiguration.return_value = []
            
            # Mock英文route输出
            mock_route_result = MagicMock()
            mock_route_result.stdout = """
===========================================================================
Interface List
  1...........................Software Loopback Interface 1
  2...00 11 22 33 44 55 ......Intel(R) Ethernet Connection (7) I219-V
===========================================================================
IPv4 Route Table
===========================================================================
Active Routes:
Network Destination        Netmask          Gateway       Interface  Metric
          0.0.0.0          0.0.0.0      192.168.1.1    192.168.1.100     25
        127.0.0.0        255.0.0.0         On-link         127.0.0.1    331
        127.0.0.1  255.255.255.255         On-link         127.0.0.1    331
   192.168.1.0    255.255.255.0         On-link     192.168.1.100    281
   192.168.1.100  255.255.255.255         On-link     192.168.1.100    281
   192.168.1.255  255.255.255.255         On-link     192.168.1.100    281
===========================================================================
"""
            mock_route_result.returncode = 0
            
            # Mock英文ipconfig输出
            mock_ipconfig_result = MagicMock()
            mock_ipconfig_result.stdout = """
Windows IP Configuration

Ethernet adapter Ethernet:

   Connection-specific DNS Suffix  . : local
   Description . . . . . . . . . . . : Intel(R) Ethernet Connection (7) I219-V
   Physical Address. . . . . . . . . : 00-11-22-33-44-55
   DHCP Enabled. . . . . . . . . . . : Yes
   Autoconfiguration Enabled . . . . : Yes
   Link-local IPv6 Address . . . . . : fe80::1234%2(Preferred)
   IPv4 Address. . . . . . . . . . . : 192.168.1.100(Preferred)
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 192.168.1.1
   DHCP Server . . . . . . . . . . . : 192.168.1.1
   DNS Servers . . . . . . . . . . . : 8.8.8.8
                                       8.8.4.4
"""
            mock_ipconfig_result.returncode = 0
            
            mock_subprocess.side_effect = [
                mock_route_result,
                mock_ipconfig_result,
                MagicMock(),  # nslookup
                MagicMock(),  # netsh
                MagicMock(),  # netstat
                MagicMock()   # arp
            ]
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            # 英文输出应该也能正确解析
            assert "routing_table" in response.data
    
    @pytest.mark.asyncio
    async def test_windows_system_timeout(self):
        """测试采集超时"""
        request = ToolRequest(parameters={})
        
        with patch('wmi.WMI') as mock_wmi_class, \
             patch('subprocess.run') as mock_subprocess:
            
            # Mock subprocess.run超时
            mock_subprocess.side_effect = subprocess.TimeoutExpired("route", 30)
            
            response = await self.tool.execute(request, self.ctx)
            
            # 超时应该被捕获，工具返回成功但数据可能不完整
            assert response.success is True
            # 验证返回的数据结构
            assert isinstance(response.data, dict)