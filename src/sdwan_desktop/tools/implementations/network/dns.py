"""
DNS工具 - DNS解析测试

遵循 SDWAN_SPEC.md §2.4.1 工具约束
遵循 SDWAN_SPEC_PATCHES.md PATCH-003 装饰器规范
"""

import asyncio
import logging
import socket
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.tool import ToolRequest, ToolResponse
from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.tools.registry.decorator import tool_function

logger = logging.getLogger(__name__)


@tool_function(
    name="dns",
    description="DNS解析测试，支持多种记录类型",
    timeout=10,
    retry_count=1,
    input_schema={
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "要解析的域名"},
            "dns_server": {"type": "string", "description": "指定DNS服务器IP地址"},
            "record_type": {
                "type": "string", 
                "enum": ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR"],
                "default": "A"
            },
            "timeout": {"type": "integer", "minimum": 1, "maximum": 30, "default": 5},
        },
        "required": ["domain"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "domain": {"type": "string", "description": "查询的域名"},
            "record_type": {"type": "string", "description": "记录类型"},
            "resolved_ips": {
                "type": "array",
                "items": {"type": "string"},
                "description": "解析的IP地址列表"
            },
            "cnames": {
                "type": "array",
                "items": {"type": "string"},
                "description": "CNAME记录列表"
            },
            "mx_records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "preference": {"type": "integer", "description": "优先级"},
                        "exchange": {"type": "string", "description": "邮件服务器"},
                    }
                },
                "description": "MX记录列表"
            },
            "ns_records": {
                "type": "array",
                "items": {"type": "string"},
                "description": "NS记录列表"
            },
            "txt_records": {
                "type": "array",
                "items": {"type": "string"},
                "description": "TXT记录列表"
            },
            "response_time_ms": {"type": "number", "description": "响应时间(ms)"},
            "ttl": {"type": "integer", "description": "TTL值"},
            "dns_server_used": {"type": "string", "description": "使用的DNS服务器"},
            "error_code": {"type": "string", "description": "DNS错误码"},
        },
        "required": ["success", "domain", "record_type", "response_time_ms"],
    },
)
class DnsTool:
    """DNS解析工具
    
    使用dnspython库进行DNS查询
    支持自定义DNS服务器和多种记录类型
    """
    
    def __init__(self):
        self._dns_available = self._check_dnspython()
    
    def _check_dnspython(self) -> bool:
        """检查dnspython库是否可用"""
        try:
            import dns.resolver
            return True
        except ImportError:
            logger.warning("dnspython库未安装，将使用系统DNS解析")
            return False
    
    async def execute(self, request: ToolRequest, ctx: FlowContext) -> ToolResponse:
        """执行DNS解析
        
        Args:
            request: 工具请求，parameters包含:
                - domain: str (必填) 要解析的域名
                - dns_server: str (可选) 指定DNS服务器
                - record_type: str (可选) 记录类型，默认A
                - timeout: int (可选) 超时秒数，默认5
            ctx: 流程上下文
            
        Returns:
            ToolResponse: 解析结果
        """
        # 1. 参数解析
        params = request.parameters
        domain = params.get("domain")
        dns_server = params.get("dns_server")
        record_type = params.get("record_type", "A")
        timeout = params.get("timeout", 5)
        
        # 2. 参数校验
        if not domain:
            return ToolResponse(
                success=False,
                error_code="VAL_002",
                error_message="缺少必填参数: domain",
                trace_id=ctx.trace_id
            )
        
        valid_record_types = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR"]
        if record_type not in valid_record_types:
            return ToolResponse(
                success=False,
                error_code="VAL_001",
                error_message=f"record_type必须是以下之一: {', '.join(valid_record_types)}",
                trace_id=ctx.trace_id
            )
        
        # 3. 执行解析
        try:
            logger.info(
                f"开始DNS解析: {domain}, type={record_type}, "
                f"dns_server={dns_server or '系统默认'}",
                extra={"trace_id": ctx.trace_id}
            )
            
            start_time = asyncio.get_event_loop().time()
            
            if self._dns_available:
                result = await self._resolve_with_dnspython(
                    domain, record_type, dns_server, timeout
                )
            else:
                result = await self._resolve_with_system(
                    domain, record_type, dns_server, timeout
                )
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # 4. 构建响应
            result["response_time_ms"] = duration_ms
            result["domain"] = domain
            result["record_type"] = record_type
            result["dns_server_used"] = dns_server or "系统默认"
            
            logger.info(
                f"DNS解析完成: {domain}, type={record_type}, "
                f"IPs={len(result.get('resolved_ips', []))}, "
                f"time={duration_ms:.1f}ms",
                extra={"trace_id": ctx.trace_id}
            )
            
            return ToolResponse(
                success=True,
                data=result,
                trace_id=ctx.trace_id,
                duration_ms=duration_ms
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"DNS解析 {domain} 超时", extra={"trace_id": ctx.trace_id})
            return ToolResponse(
                success=False,
                error_code="TOOL_TIMEOUT",
                error_message=f"DNS解析 {domain} 超时 ({timeout}s)",
                trace_id=ctx.trace_id
            )
        except Exception as e:
            logger.error(f"DNS解析失败: {e}", extra={"trace_id": ctx.trace_id})
            return ToolResponse(
                success=False,
                error_code="TOOL_002",
                error_message=str(e),
                trace_id=ctx.trace_id
            )
    
    async def _resolve_with_dnspython(
        self,
        domain: str,
        record_type: str,
        dns_server: Optional[str],
        timeout: int
    ) -> Dict[str, Any]:
        """使用dnspython库进行DNS解析
        
        Args:
            domain: 域名
            record_type: 记录类型
            dns_server: DNS服务器
            timeout: 超时时间
            
        Returns:
            解析结果字典
        """
        import dns.resolver
        import dns.exception
        
        result = {
            "success": False,
            "resolved_ips": [],
            "cnames": [],
            "mx_records": [],
            "ns_records": [],
            "txt_records": [],
            "ttl": None,
            "error_code": None,
        }
        
        try:
            # 创建解析器
            resolver = dns.resolver.Resolver()
            resolver.timeout = timeout
            resolver.lifetime = timeout
            
            if dns_server:
                resolver.nameservers = [dns_server]
            
            # 执行查询
            if record_type == "A":
                answers = resolver.resolve(domain, "A")
                result["resolved_ips"] = [str(r) for r in answers]
                result["ttl"] = answers.rrset.ttl if answers.rrset else None
                
            elif record_type == "AAAA":
                answers = resolver.resolve(domain, "AAAA")
                result["resolved_ips"] = [str(r) for r in answers]
                result["ttl"] = answers.rrset.ttl if answers.rrset else None
                
            elif record_type == "CNAME":
                answers = resolver.resolve(domain, "CNAME")
                result["cnames"] = [str(r.target) for r in answers]
                result["ttl"] = answers.rrset.ttl if answers.rrset else None
                
            elif record_type == "MX":
                answers = resolver.resolve(domain, "MX")
                result["mx_records"] = [
                    {"preference": r.preference, "exchange": str(r.exchange)}
                    for r in answers
                ]
                result["ttl"] = answers.rrset.ttl if answers.rrset else None
                
            elif record_type == "NS":
                answers = resolver.resolve(domain, "NS")
                result["ns_records"] = [str(r.target) for r in answers]
                result["ttl"] = answers.rrset.ttl if answers.rrset else None
                
            elif record_type == "TXT":
                answers = resolver.resolve(domain, "TXT")
                result["txt_records"] = [
                    r.strings[0].decode('utf-8') if r.strings else ""
                    for r in answers
                ]
                result["ttl"] = answers.rrset.ttl if answers.rrset else None
                
            elif record_type == "SOA":
                answers = resolver.resolve(domain, "SOA")
                if answers:
                    soa = answers[0]
                    result["resolved_ips"] = [str(soa.mname)]
                    result["ttl"] = answers.rrset.ttl if answers.rrset else None
                    
            elif record_type == "PTR":
                # PTR记录需要反向解析
                answers = resolver.resolve(domain, "PTR")
                result["resolved_ips"] = [str(r.target) for r in answers]
                result["ttl"] = answers.rrset.ttl if answers.rrset else None
            
            result["success"] = True
            
        except dns.resolver.NXDOMAIN:
            result["error_code"] = "NXDOMAIN"
            result["success"] = False
        except dns.resolver.NoAnswer:
            result["error_code"] = "NOANSWER"
            result["success"] = False
        except dns.resolver.Timeout:
            result["error_code"] = "TIMEOUT"
            result["success"] = False
        except dns.exception.DNSException as e:
            result["error_code"] = "DNS_ERROR"
            result["success"] = False
            raise Exception(f"DNS错误: {e}")
        
        return result
    
    async def _resolve_with_system(
        self,
        domain: str,
        record_type: str,
        dns_server: Optional[str],
        timeout: int
    ) -> Dict[str, Any]:
        """使用系统socket进行DNS解析（备选方案）
        
        Args:
            domain: 域名
            record_type: 记录类型
            dns_server: DNS服务器
            timeout: 超时时间
            
        Returns:
            解析结果字典
        """
        result = {
            "success": False,
            "resolved_ips": [],
            "cnames": [],
            "mx_records": [],
            "ns_records": [],
            "txt_records": [],
            "ttl": None,
            "error_code": None,
        }
        
        try:
            # 只支持A和AAAA记录的系统解析
            if record_type not in ["A", "AAAA"]:
                raise Exception(f"系统DNS解析不支持 {record_type} 记录类型")
            
            # 设置socket超时
            socket.setdefaulttimeout(timeout)
            
            # 执行解析
            if record_type == "A":
                # IPv4解析
                try:
                    addrinfo = socket.getaddrinfo(
                        domain, None, 
                        socket.AF_INET, socket.SOCK_STREAM
                    )
                    result["resolved_ips"] = list(set(
                        info[4][0] for info in addrinfo
                    ))
                    result["success"] = True
                except socket.gaierror as e:
                    result["error_code"] = str(e.errno)
                    result["success"] = False
                    
            elif record_type == "AAAA":
                # IPv6解析
                try:
                    addrinfo = socket.getaddrinfo(
                        domain, None, 
                        socket.AF_INET6, socket.SOCK_STREAM
                    )
                    result["resolved_ips"] = list(set(
                        info[4][0] for info in addrinfo
                    ))
                    result["success"] = True
                except socket.gaierror as e:
                    result["error_code"] = str(e.errno)
                    result["success"] = False
            
        except Exception as e:
            result["error_code"] = "SYSTEM_ERROR"
            result["success"] = False
            raise Exception(f"系统DNS解析失败: {e}")
        
        return result
    
    def _get_default_dns_servers(self) -> List[str]:
        """获取系统默认DNS服务器
        
        Returns:
            DNS服务器列表
        """
        try:
            import dns.resolver
            resolver = dns.resolver.Resolver()
            return resolver.nameservers
        except:
            # 常见公共DNS服务器
            return [
                "8.8.8.8",      # Google DNS
                "1.1.1.1",      # Cloudflare DNS
                "114.114.114.114",  # 114DNS
                "223.5.5.5",    # 阿里DNS
            ]