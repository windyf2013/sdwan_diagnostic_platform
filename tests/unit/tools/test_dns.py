"""DnsTool单元测试"""

from unittest.mock import MagicMock, patch
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
        request = ToolRequest(parameters={
            "domain": "google.com",
            "record_type": "A"
        })
        
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            # Mock DNS响应
            mock_answer = MagicMock()
            mock_answer.rrset = MagicMock()
            mock_answer.rrset.items = ["8.8.8.8", "8.8.4.4"]
            mock_answer.response.time = 0.05  # 50ms
            
            mock_resolver.resolve.return_value = mock_answer
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            assert response.data["resolved_ips"] == ["8.8.8.8", "8.8.4.4"]
            assert response.data["response_time_ms"] == 50.0
            assert response.data["record_type"] == "A"
    
    @pytest.mark.asyncio
    async def test_dns_with_custom_server(self):
        """测试使用自定义DNS服务器"""
        request = ToolRequest(parameters={
            "domain": "example.com",
            "dns_server": "1.1.1.1",
            "record_type": "A"
        })
        
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            mock_answer = MagicMock()
            mock_answer.rrset = MagicMock()
            mock_answer.rrset.items = ["93.184.216.34"]
            mock_answer.response.time = 0.03
            
            mock_resolver.resolve.return_value = mock_answer
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            # 验证使用了自定义DNS服务器
            mock_resolver_class.assert_called_once()
            assert mock_resolver.nameservers == ["1.1.1.1"]
    
    @pytest.mark.asyncio
    async def test_dns_missing_domain(self):
        """测试缺少domain参数"""
        request = ToolRequest(parameters={})
        
        response = await self.tool.execute(request, self.ctx)
        
        assert response.success is False
        assert response.error_code == "VAL_002"
    
    @pytest.mark.asyncio
    async def test_dns_timeout(self):
        """测试DNS查询超时"""
        request = ToolRequest(parameters={"domain": "slow-domain.com"})
        
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            mock_resolver.resolve.side_effect = TimeoutError("DNS query timed out")
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_TIMEOUT"
    
    @pytest.mark.asyncio
    async def test_dns_nxdomain(self):
        """测试域名不存在"""
        request = ToolRequest(parameters={"domain": "nonexistent-domain.local"})
        
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            from dns.resolver import NXDOMAIN
            mock_resolver.resolve.side_effect = NXDOMAIN
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_002"
            assert "NXDOMAIN" in response.error_message
    
    @pytest.mark.asyncio
    async def test_dns_cname_record(self):
        """测试CNAME记录解析"""
        request = ToolRequest(parameters={
            "domain": "www.github.com",
            "record_type": "CNAME"
        })
        
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            mock_answer = MagicMock()
            mock_answer.rrset = MagicMock()
            mock_answer.rrset.items = ["github.com"]
            mock_answer.response.time = 0.02
            
            mock_resolver.resolve.return_value = mock_answer
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            assert response.data["resolved_ips"] == ["github.com"]
            assert response.data["record_type"] == "CNAME"
    
    @pytest.mark.asyncio
    async def test_dns_mx_record(self):
        """测试MX记录解析"""
        request = ToolRequest(parameters={
            "domain": "gmail.com",
            "record_type": "MX"
        })
        
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            mock_answer = MagicMock()
            mock_answer.rrset = MagicMock()
            mock_answer.rrset.items = [
                MagicMock(preference=10, exchange="alt1.gmail-smtp-in.l.google.com"),
                MagicMock(preference=20, exchange="alt2.gmail-smtp-in.l.google.com")
            ]
            mock_answer.response.time = 0.04
            
            mock_resolver.resolve.return_value = mock_answer
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is True
            assert len(response.data["resolved_ips"]) == 2
            assert "alt1.gmail-smtp-in.l.google.com" in str(response.data["resolved_ips"][0])
            assert response.data["record_type"] == "MX"
    
    @pytest.mark.asyncio
    async def test_dns_invalid_record_type(self):
        """测试无效的记录类型"""
        request = ToolRequest(parameters={
            "domain": "example.com",
            "record_type": "INVALID"
        })
        
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            from dns.resolver import NoAnswer
            mock_resolver.resolve.side_effect = NoAnswer
            
            response = await self.tool.execute(request, self.ctx)
            
            assert response.success is False
            assert response.error_code == "TOOL_002"