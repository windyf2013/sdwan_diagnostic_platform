# DNS探测规范

## 概述
本规范定义SD-WAN诊断平台的DNS探测功能，包括域名解析、DNS服务器测试、记录类型查询和性能测量。

## 协议标准

### DNS协议版本
- **DNS over UDP**：传统DNS协议，端口53
- **DNS over TCP**：TCP传输，端口53，用于大响应
- **DNS over TLS (DoT)**：加密DNS，端口853
- **DNS over HTTPS (DoH)**：HTTPS传输，端口443

### 支持的DNS记录类型
| 记录类型 | 类型值 | 用途 |
|----------|--------|------|
| A | 1 | IPv4地址记录 |
| AAAA | 28 | IPv6地址记录 |
| CNAME | 5 | 规范名称记录 |
| MX | 15 | 邮件交换记录 |
| TXT | 16 | 文本记录 |
| NS | 2 | 名称服务器记录 |
| PTR | 12 | 指针记录 |
| SOA | 6 | 起始授权记录 |
| SRV | 33 | 服务定位记录 |

## 探测参数

### 基本参数
```python
@dataclass
class DnsProbeParameters:
    """DNS探测参数"""
    # 查询信息
    domain_name: str                    # 查询的域名
    record_type: str = "A"              # 记录类型：A/AAAA/MX/TXT等
    query_class: str = "IN"             # 查询类：IN/CH/HS
    
    # DNS服务器配置
    dns_server: Optional[str] = None    # 指定DNS服务器（IP:端口）
    dns_servers: List[str] = field(default_factory=list)  # 多个DNS服务器
    use_system_dns: bool = True         # 是否使用系统DNS配置
    
    # 传输配置
    protocol: str = "udp"               # 协议：udp/tcp/dot/doh
    timeout_ms: int = 5000              # 查询超时（毫秒）
    retry_count: int = 2                # 重试次数
    
    # 高级配置
    edns_enabled: bool = True           # 是否启用EDNS
    dnssec_enabled: bool = False        # 是否启用DNSSEC验证
    recursive_query: bool = True        # 是否递归查询
    
    # 缓存配置
    use_cache: bool = True              # 是否使用缓存
    cache_ttl: int = 300                # 缓存TTL（秒）
    
    # 安全配置
    validate_response: bool = True      # 是否验证响应
    check_spoofing: bool = True         # 是否检查DNS欺骗
```

### 参数约束
1. **timeout_ms**：100-30000毫秒，默认5000毫秒
2. **retry_count**：0-5次，默认2次
3. **cache_ttl**：0-86400秒，默认300秒
4. **record_type**：支持的标准DNS记录类型

## 数据模型

### 探测结果
```python
@dataclass
class DnsProbeResult:
    """DNS探测结果"""
    # 基本信息
    probe_id: str                       # 探测ID
    trace_id: str                       # 追踪ID
    timestamp: datetime                 # 探测时间
    
    # 查询信息
    domain_name: str                    # 查询的域名
    record_type: str                    # 记录类型
    query_class: str                    # 查询类
    
    # DNS服务器信息
    dns_server_used: str                # 使用的DNS服务器
    dns_servers_tried: List[str]        # 尝试的DNS服务器列表
    protocol_used: str                  # 使用的协议
    
    # 解析结果
    success: bool                       # 查询是否成功
    response_code: str                  # DNS响应码：NOERROR/NXDOMAIN/SERVFAIL等
    authoritative: bool                 # 是否权威应答
    
    # 记录数据
    answers: List[DnsRecord]            # 答案部分记录
    authorities: List[DnsRecord]        # 权威部分记录
    additionals: List[DnsRecord]        # 附加部分记录
    
    # 性能指标
    query_time_ms: float                # 查询耗时（毫秒）
    total_time_ms: float                # 总耗时（包括重试）
    retry_count: int = 0                # 重试次数
    
    # 缓存信息
    cached: bool = False                # 是否来自缓存
    cache_ttl: Optional[int] = None     # 缓存剩余TTL
    
    # DNSSEC信息
    dnssec_enabled: bool = False        # 是否启用DNSSEC
    dnssec_valid: Optional[bool] = None # DNSSEC验证结果
    dnssec_rrsig: Optional[str] = None  # RRSIG记录
    
    # 错误信息
    error_message: Optional[str] = None # 错误信息
    error_code: Optional[str] = None    # 错误代码
    exception_type: Optional[str] = None  # 异常类型
```

### DNS记录
```python
@dataclass
class DnsRecord:
    """DNS记录"""
    # 记录基本信息
    name: str                           # 记录名称
    record_type: str                    # 记录类型
    record_class: str                   # 记录类
    ttl: int                            # TTL值（秒）
    
    # 记录数据（根据类型不同）
    data: Any                           # 记录数据
    
    # 类型特定字段
    @property
    def ip_address(self) -> Optional[str]:
        """获取IP地址（A/AAAA记录）"""
        if self.record_type in ["A", "AAAA"]:
            return str(self.data)
        return None
    
    @property
    def canonical_name(self) -> Optional[str]:
        """获取规范名称（CNAME记录）"""
        if self.record_type == "CNAME":
            return str(self.data)
        return None
    
    @property
    def mail_exchange(self) -> Optional[tuple]:
        """获取邮件交换记录（MX记录）"""
        if self.record_type == "MX":
            return self.data  # (priority, exchange)
        return None
    
    @property
    def text_data(self) -> Optional[str]:
        """获取文本数据（TXT记录）"""
        if self.record_type == "TXT":
            return self.data
        return None
```

### DNS服务器测试结果
```python
@dataclass
class DnsServerTestResult:
    """DNS服务器测试结果"""
    # 服务器信息
    server_address: str                 # 服务器地址（IP:端口）
    protocol: str                       # 测试协议
    
    # 测试结果
    reachable: bool                     # 是否可达
    response_time_ms: Optional[float]   # 响应时间（毫秒）
    success_rate: float                 # 成功率（0-1）
    
    # 功能测试
    supports_recursion: Optional[bool] = None  # 是否支持递归
    supports_edns: Optional[bool] = None       # 是否支持EDNS
    supports_dnssec: Optional[bool] = None     # 是否支持DNSSEC
    
    # 安全测试
    supports_dot: Optional[bool] = None        # 是否支持DoT
    supports_doh: Optional[bool] = None        # 是否支持DoH
    validates_dnssec: Optional[bool] = None    # 是否验证DNSSEC
    
    # 性能指标
    avg_response_time_ms: Optional[float] = None  # 平均响应时间
    max_response_time_ms: Optional[float] = None  # 最大响应时间
    min_response_time_ms: Optional[float] = None  # 最小响应时间
    
    # 错误信息
    errors: List[str] = field(default_factory=list)  # 错误列表
    last_error: Optional[str] = None    # 最后错误
```

## 实现要求

### 平台兼容性
| 平台 | 实现方式 | 备注 |
|------|----------|------|
| 所有平台 | 使用 `dnspython` 库 | 功能最完整的DNS库 |
| 备选方案 | 使用 `aiodns` 库 | 异步DNS查询 |
| 简单查询 | 使用系统解析器 | 功能有限，但简单 |

### 传输协议支持
1. **UDP DNS**：基本实现，支持大多数场景
2. **TCP DNS**：大响应或需要可靠传输时使用
3. **DNS over TLS**：加密传输，需要证书验证
4. **DNS over HTTPS**：HTTPS传输，绕过网络限制

### 代码示例
```python
@tool_function(
    name="dns_query",
    description="DNS查询工具",
    timeout=30,
    retry_count=2
)
class DnsQueryTool:
    """DNS查询工具"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.resolver = dns.resolver.Resolver()
        self.cache = {}
        
        # 配置解析器
        if self.config.get("dns_servers"):
            self.resolver.nameservers = self.config["dns_servers"]
        
        self.resolver.timeout = self.config.get("timeout", 5)
        self.resolver.lifetime = self.config.get("lifetime", 10)
    
    async def execute(self, request: ToolRequest, ctx: Context) -> ToolResponse:
        """执行DNS查询"""
        # 参数验证
        params = self._validate_parameters(request.parameters)
        
        # 检查缓存
        cache_key = self._get_cache_key(params)
        if params.use_cache and cache_key in self.cache:
            cached_result = self.cache[cache_key]
            if time.time() < cached_result["expires"]:
                cached_result["cached"] = True
                return ToolResponse(
                    success=True,
                    data=cached_result["data"],
                    trace_id=ctx.trace_id
                )
        
        # 执行查询
        start_time = time.time()
        result = await self._perform_query(params, ctx.trace_id)
        query_time = (time.time() - start_time) * 1000
        
        # 更新结果
        result.query_time_ms = query_time
        result.total_time_ms = query_time
        
        # 更新缓存
        if params.use_cache and result.success:
            self.cache[cache_key] = {
                "data": result.to_dict(),
                "expires": time.time() + params.cache_ttl
            }
        
        return ToolResponse(
            success=True,
            data=result.to_dict(),
            trace_id=ctx.trace_id
        )
    
    async def _perform_query(self, params: DnsProbeParameters, trace_id: str) -> DnsProbeResult:
        """执行实际的DNS查询"""
        # 根据协议选择查询方法
        if params.protocol == "doh":
            return await self._query_doh(params, trace_id)
        elif params.protocol == "dot":
            return await self._query_dot(params, trace_id)
        elif params.protocol == "tcp":
            return await self._query_tcp(params, trace_id)
        else:  # udp
            return await self._query_udp(params, trace_id)
    
    async def _query_udp(self, params: DnsProbeParameters, trace_id: str) -> DnsProbeResult:
        """UDP DNS查询"""
        try:
            # 设置查询参数
            if params.dns_server:
                resolver = dns.resolver.Resolver()
                resolver.nameservers = [params.dns_server]
                resolver.timeout = params.timeout_ms / 1000
                resolver.lifetime = params.timeout_ms / 1000 * (params.retry_count + 1)
            else:
                resolver = self.resolver
            
            # 执行查询
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: resolver.resolve(
                    params.domain_name,
                    params.record_type,
                    params.query_class
                )
            )
            
            # 构建结果
            return DnsProbeResult(
                probe_id=str(uuid.uuid4()),
                trace_id=trace_id,
                timestamp=datetime.now(),
                domain_name=params.domain_name,
                record_type=params.record_type,
                query_class=params.query_class,
                dns_server_used=resolver.nameservers[0] if resolver.nameservers else "system",
                success=True,
                response_code="NOERROR",
                authoritative=response.response.flags & dns.flags.AA != 0,
                answers=self._parse_records(response.response.answer),
                authorities=self._parse_records(response.response.authority),
                additionals=self._parse_records(response.response.additional),
                dnssec_enabled=params.dnssec_enabled,
                dnssec_valid=self._validate_dnssec(response) if params.dnssec_enabled else None
            )
            
        except dns.resolver.NXDOMAIN:
            return self._build_nxdomain_result(params, trace_id)
        except dns.resolver.Timeout:
            return self._build_timeout_result(params, trace_id)
        except dns.resolver.NoNameservers:
            return self._build_no_nameservers_result(params, trace_id)
        except Exception as e:
            return self._build_error_result(params, str(e), trace_id)
```

## 错误处理

### 错误分类
| 错误类型 | 错误代码 | 描述 | 处理建议 |
|----------|----------|------|----------|
| NXDOMAIN | DNS_NXDOMAIN | 域名不存在 | 检查域名拼写或注册状态 |
| SERVFAIL | DNS_SERVFAIL | 服务器失败 | DNS服务器配置问题 |
| REFUSED | DNS_REFUSED | 查询被拒绝 | 检查DNS服务器ACL |
| 超时 | DNS_TIMEOUT | 查询超时 | 检查网络连接或增加超时时间 |
| 无名称服务器 | DNS_NO_NAMESERVERS | 无可用名称服务器 | 检查DNS服务器配置 |
| 格式错误 | DNS_FORMAT_ERROR | 查询格式错误 | 检查查询参数 |
| 不支持 | DNS_NOT_IMPLEMENTED | 不支持的操作 | 检查记录类型支持 |

### 错误恢复策略
1. **重试机制**：可配置的重试次数和退避策略
2. **服务器轮询**：多个DNS服务器轮询查询
3. **协议降级**：DoH/DoT失败时降级到UDP/TCP
4. **缓存回退**：查询失败时返回缓存结果（如果可用）

## 性能要求

### 响应时间
| 场景 | 最大响应时间 | 说明 |
|------|--------------|------|
| 本地缓存查询 | < 1ms | 直接从内存缓存返回 |
| 本地递归查询 | < 100ms | 本地DNS服务器查询 |
| 远程权威查询 | < 500ms | 跨网络权威服务器查询 |
| DoH/DoT查询 | < 1000ms | 加密传输额外开销 |

### 资源使用
| 资源 | 限制 | 说明 |
|------|------|------|
| 内存 | < 5MB/并发查询 | 包括缓存和结果存储 |
| 网络连接 | < 50个并发连接 | 限制到DNS服务器的连接数 |
| 缓存大小 | < 100MB | DNS缓存最大大小 |

## 安全考虑

### 安全限制
1. **查询限制**：限制每秒查询次数
2. **域名限制**：支持白名单/黑名单过滤
3. **记录类型限制**：限制可查询的记录类型
4. **响应大小限制**：限制DNS响应大小，防止放大攻击

### 隐私保护
1. **查询加密**：优先使用DoH/DoT加密查询
2. **日志脱敏**：不记录敏感域名查询
3. **缓存隔离**：不同用户/会话的缓存隔离
4. **查询最小化**：仅查询必要的信息

### DNSSEC验证
1. **签名验证**：验证RRSIG记录
2. **链式验证**：验证信任链完整性
3. **过期检查**：检查签名过期时间
4. **失败处理**：DNSSEC验证失败时的处理策略

## 配置管理

### 配置文件
```yaml
dns_probe:
  # 基本配置
  default_timeout_ms: 5000
  default_retry_count: 2
  default_record_type: "A"
  
  # DNS服务器配置
  system_dns_enabled: true
  fallback_dns_servers:
    - "8.8.8.8"      # Google DNS
    - "1.1.1.1"      # Cloudflare DNS
    - "114.114.114.114"  # 114DNS
  
  # 缓存配置
  cache_enabled: true
  cache_size_mb: 50
  default_cache_ttl: 300
  negative_cache_ttl: 60
  
  # 安全配置
  prefer_encrypted: true  # 优先使用DoH/DoT
  dnssec_validation: false  # 默认不验证DNSSEC
  rate_limit_per_second: 100
  
  # DoH配置
  doh_servers:
    - "https://dns.google/dns-query"
    - "https://cloudflare-dns.com/dns-query"
    - "https://dns.alidns.com/dns-query"
  
  # DoT配置
  dot_servers:
    - "dns.google:853"
    - "1.1.1.1:853"
    - "dot.pub:853"
  
  # 查询限制
  max_query_length: 253  # 域名最大长度
  allowed_record_types: ["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA"]
  restricted_domains: []