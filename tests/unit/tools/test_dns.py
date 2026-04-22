"""DnsTool单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from sdwan_desktop.core.types.tool import ToolRequest
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.implementations.network.dns import DnsTool


class TestDnsTool:
    """DnsTool测试类"""
    
    def setup_method(self):
        """测试初始化"""
        self.tool = DnsTool()
        self.ctx = FlowContext(
            flow_id="test-flow",
            flow_name="test",
            trace_id="test-trace-123"
        )
    
    @pytest.mark.asyncio
    async def test_dns_resolve_success(self):
        """测试DNS解析成功"""
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "google.com",
                "record_type": "A"
            }
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "success": True,
                "resolved_ips": ["142.250.80.46"],
                "cnames": [],
                "mx_records": [],
                "ns_records": [],
                "txt_records": [],
                "ttl": 300,
                "error_code": None,
            }
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True
            assert "142.250.80.46" in response.data["resolved_ips"]
            assert response.data["domain"] == "google.com"
            assert response.data["record_type"] == "A"
    
    @pytest.mark.asyncio
    async def test_dns_with_custom_server(self):
        """测试使用自定义DNS服务器"""
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "example.com",
                "dns_server": "1.1.1.1",
                "record_type": "A"
            }
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "success": True,
                "resolved_ips": ["93.184.216.34"],
                "cnames": [],
                "mx_records": [],
                "ns_records": [],
                "txt_records": [],
                "ttl": 300,
                "error_code": None,
            }
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True
            assert response.data["dns_server_used"] == "1.1.1.1"
    
    @pytest.mark.asyncio
    async def test_dns_missing_domain(self):
        """测试缺少domain参数"""
        request = ToolRequest(
            tool_name="dns",
            parameters={}
        )
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
    
    @pytest.mark.asyncio
    async def test_dns_timeout(self):
        """测试DNS查询超时"""
        request = ToolRequest(
            tool_name="dns",
            parameters={"domain": "slow-domain.com"}
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = __import__('asyncio').TimeoutError("超时")
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is False
            assert response.error_code == "TOOL_TIMEOUT"
    
    @pytest.mark.asyncio
    async def test_dns_nxdomain(self):
        """测试域名不存在"""
        request = ToolRequest(
            tool_name="dns",
            parameters={"domain": "nonexistent-domain.local"}
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "success": False,
                "resolved_ips": [],
                "cnames": [],
                "mx_records": [],
                "ns_records": [],
                "txt_records": [],
                "ttl": None,
                "error_code": "NXDOMAIN",
            }
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True  # 工具执行成功，但DNS查询失败
            assert response.data["error_code"] == "NXDOMAIN"
    
    @pytest.mark.asyncio
    async def test_dns_cname_record(self):
        """测试CNAME记录解析"""
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "www.github.com",
                "record_type": "CNAME"
            }
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "success": True,
                "resolved_ips": [],
                "cnames": ["github.com"],
                "mx_records": [],
                "ns_records": [],
                "txt_records": [],
                "ttl": 3600,
                "error_code": None,
            }
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True
            assert "github.com" in response.data["cnames"]
    
    @pytest.mark.asyncio
    async def test_dns_mx_record(self):
        """测试MX记录解析"""
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "gmail.com",
                "record_type": "MX"
            }
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "success": True,
                "resolved_ips": [],
                "cnames": [],
                "mx_records": [{"preference": 10, "exchange": "alt1.gmail-smtp-in.l.google.com"}],
                "ns_records": [],
                "txt_records": [],
                "ttl": 3600,
                "error_code": None,
            }
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True
            assert len(response.data["mx_records"]) > 0
    
    @pytest.mark.asyncio
    async def test_dns_invalid_record_type(self):
        """测试无效的记录类型"""
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "example.com",
                "record_type": "INVALID"
            }
        )
        
        response = await self.tool.execute(request, self.ctx)
        
        # 无效记录类型应该在参数校验阶段就失败
        assert response.success is False
        assert response.error_code == "VAL_001"

    @pytest.mark.asyncio
    async def test_dns_aaaa_record(self):
        """测试AAAA记录解析"""
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "google.com",
                "record_type": "AAAA"
            }
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "success": True,
                "resolved_ips": ["2001:4860:4860::8888"],
                "cnames": [],
                "mx_records": [],
                "ns_records": [],
                "txt_records": [],
                "ttl": 300,
                "error_code": None,
            }
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True
            assert "2001:4860:4860::8888" in response.data["resolved_ips"]

    @pytest.mark.asyncio
    async def test_dns_ns_record(self):
        """测试NS记录解析"""
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "google.com",
                "record_type": "NS"
            }
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "success": True,
                "resolved_ips": [],
                "cnames": [],
                "mx_records": [],
                "ns_records": ["ns1.google.com"],
                "txt_records": [],
                "ttl": 86400,
                "error_code": None,
            }
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True
            assert "ns1.google.com" in response.data["ns_records"]

    @pytest.mark.asyncio
    async def test_dns_txt_record(self):
        """测试TXT记录解析"""
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "google.com",
                "record_type": "TXT"
            }
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "success": True,
                "resolved_ips": [],
                "cnames": [],
                "mx_records": [],
                "ns_records": [],
                "txt_records": ["v=spf1 include:_spf.google.com ~all"],
                "ttl": 3600,
                "error_code": None,
            }
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True
            assert len(response.data["txt_records"]) > 0

    @pytest.mark.asyncio
    async def test_dns_soa_record(self):
        """测试SOA记录解析"""
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "google.com",
                "record_type": "SOA"
            }
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "success": True,
                "resolved_ips": ["ns1.google.com"],
                "cnames": [],
                "mx_records": [],
                "ns_records": [],
                "txt_records": [],
                "ttl": 86400,
                "error_code": None,
            }
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True

    @pytest.mark.asyncio
    async def test_dns_ptr_record(self):
        """测试PTR记录解析"""
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "8.8.8.8.in-addr.arpa",
                "record_type": "PTR"
            }
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "success": True,
                "resolved_ips": ["dns.google"],
                "cnames": [],
                "mx_records": [],
                "ns_records": [],
                "txt_records": [],
                "ttl": 86400,
                "error_code": None,
            }
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True

    @pytest.mark.asyncio
    async def test_dns_general_exception(self):
        """测试通用异常"""
        request = ToolRequest(
            tool_name="dns",
            parameters={"domain": "example.com"}
        )
        
        with patch.object(self.tool, '_resolve_with_dnspython', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = Exception("DNS服务器不可达")
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is False
            assert response.error_code == "TOOL_002"

    @pytest.mark.asyncio
    async def test_dns_resolve_with_system(self):
        """测试使用系统DNS解析"""
        # 强制使用系统解析
        self.tool._dns_available = False
        
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "example.com",
                "record_type": "A"
            }
        )
        
        with patch('socket.getaddrinfo') as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, '', ('93.184.216.34', 0))
            ]
            
            response = await self.tool.execute(request, self.ctx)
            assert response.success is True
            assert "93.184.216.34" in response.data["resolved_ips"]

    @pytest.mark.asyncio
    async def test_dns_resolve_with_system_unsupported_type(self):
        """测试系统DNS解析不支持的类型"""
        self.tool._dns_available = False
        
        request = ToolRequest(
            tool_name="dns",
            parameters={
                "domain": "example.com",
                "record_type": "MX"
            }
        )
        
        response = await self.tool.execute(request, self.ctx)
        assert response.success is False
        assert response.error_code == "TOOL_002"

    def test_get_default_dns_servers(self):
        """测试获取默认DNS服务器"""
        servers = self.tool._get_default_dns_servers()
        assert len(servers) > 0
        assert isinstance(servers, list)
        assert all(isinstance(s, str) for s in servers)


    def test_check_dnspython_available(self):
        """测试dnspython检查可用"""
        tool = DnsTool()
        assert tool._dns_available is True
