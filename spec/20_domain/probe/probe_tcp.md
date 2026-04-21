# TCP探测规范

## 概述
本规范定义SD-WAN诊断平台的TCP端口探测功能，包括连接测试、端口扫描、服务识别和性能测量。

## 协议标准

### TCP协议特性
- **三次握手**：SYN → SYN-ACK → ACK
- **连接状态**：LISTEN, SYN_SENT, SYN_RECEIVED, ESTABLISHED, FIN_WAIT, CLOSE_WAIT, CLOSED
- **超时机制**：连接超时、读取超时、写入超时
- **错误处理**：连接拒绝、超时、重置、不可达

### 支持的TCP选项
| 选项 | 用途 | 默认值 |
|------|------|--------|
| SO_KEEPALIVE | 保持连接活跃 | False |
| TCP_NODELAY | 禁用Nagle算法 | True |
| SO_REUSEADDR | 地址重用 | False |
| SO_LINGER | 关闭延迟 | 关闭立即 |

## 探测参数

### 基本参数
```python
@dataclass
class TcpProbeParameters:
    """TCP探测参数"""
    # 目标信息
    target_host: str                    # 目标主机（IP或域名）
    target_ip: Optional[str] = None     # 解析后的IP地址
    target_port: int                    # 目标端口（1-65535）
    
    # 连接配置
    timeout_ms: int = 5000              # 连接超时（毫秒）
    connect_timeout_ms: int = 3000      # 连接建立超时
    read_timeout_ms: int = 5000         # 读取超时
    write_timeout_ms: int = 5000        # 写入超时
    
    # 协议配置
    protocol: str = "tcp"               # 协议类型：tcp/tls
    ssl_enabled: bool = False           # 是否启用SSL/TLS
    ssl_verify: bool = True             # 是否验证SSL证书
    
    # 数据交换
    send_data: Optional[bytes] = None   # 发送的数据
    receive_expected: Optional[bytes] = None  # 期望接收的数据
    banner_grab: bool = True            # 是否尝试获取banner
    
    # 高级配置
    source_ip: Optional[str] = None     # 源IP地址
    source_port: Optional[int] = None   # 源端口（0表示随机）
    interface: Optional[str] = None     # 网络接口
    ip_version: str = "auto"            # IP版本：auto/ipv4/ipv6
```

### 参数约束
1. **target_port**：1-65535，常用端口范围
2. **timeout_ms**：100-60000毫秒，默认5000毫秒
3. **connect_timeout_ms**：100-30000毫秒，默认3000毫秒
4. **source_port**：0-65535，0表示随机分配

## 数据模型

### 探测结果
```python
@dataclass
class TcpProbeResult:
    """TCP探测结果"""
    # 基本信息
    probe_id: str                       # 探测ID
    trace_id: str                       # 追踪ID
    timestamp: datetime                 # 探测时间
    
    # 目标信息
    target_host: str                    # 目标主机
    target_ip: str                      # 目标IP地址
    target_port: int                    # 目标端口
    resolved_ips: List[str]             # 解析的所有IP地址
    
    # 连接状态
    connection_success: bool            # 连接是否成功
    connection_state: str               # 连接状态
    connection_time_ms: Optional[float] # 连接建立时间（毫秒）
    
    # SSL/TLS信息（如果启用）
    ssl_enabled: bool = False           # 是否使用SSL
    ssl_version: Optional[str] = None   # SSL/TLS版本
    ssl_cipher: Optional[str] = None    # 加密套件
    ssl_cert_valid: Optional[bool] = None  # 证书是否有效
    ssl_cert_expiry: Optional[datetime] = None  # 证书过期时间
    
    # 数据交换信息
    data_sent: bool = False             # 是否发送了数据
    data_received: bool = False         # 是否接收了数据
    send_size: int = 0                  # 发送数据大小
    receive_size: int = 0               # 接收数据大小
    banner: Optional[str] = None        # 获取的banner信息
    
    # 性能指标
    total_duration_ms: float            # 总耗时
    dns_resolution_ms: Optional[float]  # DNS解析耗时
    ssl_handshake_ms: Optional[float]   # SSL握手耗时（如果启用）
    
    # 错误信息
    error_message: Optional[str] = None # 错误信息
    error_code: Optional[str] = None    # 错误代码
    exception_type: Optional[str] = None  # 异常类型
```

### 端口扫描结果
```python
@dataclass
class TcpPortScanResult:
    """TCP端口扫描结果"""
    # 扫描信息
    scan_id: str                        # 扫描ID
    trace_id: str                       # 追踪ID
    target_host: str                    # 目标主机
    target_ip: str                      # 目标IP地址
    
    # 扫描配置
    port_range: str                     # 端口范围（如"1-1000"）
    scan_method: str                    # 扫描方法（connect/syn）
    timeout_ms: int                     # 超时时间
    
    # 扫描结果
    ports_scanned: int                  # 扫描的端口数
    ports_open: List[TcpPortStatus]     # 开放的端口列表
    ports_filtered: List[TcpPortStatus] # 过滤的端口列表
    ports_closed: List[TcpPortStatus]   # 关闭的端口列表
    
    # 统计信息
    scan_duration_ms: float             # 扫描总耗时
    open_rate: float                    # 开放率（0-1）
    
    # 服务识别
    services_identified: List[ServiceInfo]  # 识别的服务列表
```

### 端口状态
```python
@dataclass
class TcpPortStatus:
    """TCP端口状态"""
    port: int                           # 端口号
    state: str                          # 状态：open/closed/filtered
    service: Optional[str] = None       # 服务名称
    protocol: str = "tcp"               # 协议类型
    banner: Optional[str] = None        # banner信息
    response_time_ms: Optional[float] = None  # 响应时间
    scanned_at: datetime = field(default_factory=datetime.now)
```

## 实现要求

### 平台兼容性
| 平台 | 实现方式 | 备注 |
|------|----------|------|
| Windows | 使用 `socket` 模块或 `asyncio` | 支持异步连接 |
| Linux | 使用 `socket` 模块或 `asyncio` | 支持原始套接字（需要权限） |
| macOS | 使用 `socket` 模块或 `asyncio` | 类似Linux实现 |

### 扫描方法
1. **TCP Connect扫描**：完整的三次握手，最可靠
2. **TCP SYN扫描**：半开放扫描，需要原始套接字权限
3. **TCP ACK扫描**：检测防火墙规则
4. **TCP Window扫描**：分析TCP窗口大小

### 代码示例
```python
@tool_function(
    name="tcp_port_check",
    description="TCP端口连通性检查",
    timeout=30,
    retry_count=2
)
class TcpPortCheckTool:
    """TCP端口检查工具"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.max_concurrent = self.config.get("max_concurrent", 10)
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
    
    async def execute(self, request: ToolRequest, ctx: Context) -> ToolResponse:
        """执行TCP端口检查"""
        # 参数验证
        params = self._validate_parameters(request.parameters)
        
        # 解析目标
        resolved_ips = await self._resolve_target(params.target_host)
        
        # 执行探测
        results = []
        async with self.semaphore:
            for ip in resolved_ips:
                result = await self._check_single_port(ip, params)
                results.append(result)
        
        # 合并结果
        final_result = self._merge_results(results, params)
        
        return ToolResponse(
            success=True,
            data=final_result.to_dict(),
            trace_id=ctx.trace_id
        )
    
    async def _check_single_port(self, ip: str, params: TcpProbeParameters) -> TcpProbeResult:
        """检查单个端口"""
        start_time = time.time()
        
        try:
            # 创建socket连接
            if params.ip_version == "ipv6":
                family = socket.AF_INET6
            else:
                family = socket.AF_INET
            
            # 异步连接
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    host=ip,
                    port=params.target_port,
                    family=family,
                    ssl=params.ssl_enabled,
                    ssl_handshake_timeout=params.connect_timeout_ms/1000 if params.ssl_enabled else None
                ),
                timeout=params.connect_timeout_ms/1000
            )
            
            connection_time = (time.time() - start_time) * 1000
            
            # 获取banner（如果启用）
            banner = None
            if params.banner_grab:
                try:
                    # 发送探测数据或等待初始数据
                    if params.send_data:
                        writer.write(params.send_data)
                        await writer.drain()
                    
                    # 尝试读取banner
                    await asyncio.wait_for(reader.read(1024), timeout=1.0)
                    banner_data = await reader.read(1024)
                    if banner_data:
                        banner = banner_data.decode('utf-8', errors='ignore')
                except (asyncio.TimeoutError, UnicodeDecodeError):
                    pass
            
            # 获取SSL信息（如果启用）
            ssl_info = None
            if params.ssl_enabled and writer.transport:
                ssl_object = writer.transport.get_extra_info('ssl_object')
                if ssl_object:
                    ssl_info = {
                        'version': ssl_object.version(),
                        'cipher': ssl_object.cipher(),
                        'cert': ssl_object.getpeercert()
                    }
            
            # 清理连接
            writer.close()
            await writer.wait_closed()
            
            return TcpProbeResult(
                probe_id=str(uuid.uuid4()),
                trace_id=ctx.trace_id,
                timestamp=datetime.now(),
                target_host=params.target_host,
                target_ip=ip,
                target_port=params.target_port,
                resolved_ips=[ip],
                connection_success=True,
                connection_state="ESTABLISHED",
                connection_time_ms=connection_time,
                ssl_enabled=params.ssl_enabled,
                ssl_version=ssl_info['version'] if ssl_info else None,
                ssl_cipher=ssl_info['cipher'] if ssl_info else None,
                banner=banner,
                total_duration_ms=(time.time() - start_time) * 1000
            )
            
        except asyncio.TimeoutError:
            return self._build_timeout_result(ip, params, start_time, ctx.trace_id)
        except ConnectionRefusedError:
            return self._build_connection_refused_result(ip, params, start_time, ctx.trace_id)
        except Exception as e:
            return self._build_error_result(ip, params, start_time, str(e), ctx.trace_id)
```

## 错误处理

### 错误分类
| 错误类型 | 错误代码 | 描述 | 处理建议 |
|----------|----------|------|----------|
| 连接拒绝 | TCP_CONNECTION_REFUSED | 目标端口拒绝连接 | 端口未开放或服务未运行 |
| 连接超时 | TCP_CONNECTION_TIMEOUT | 连接建立超时 | 检查防火墙或网络路径 |
| 主机不可达 | TCP_HOST_UNREACHABLE | 目标主机不可达 | 检查网络连接和路由 |
| 端口过滤 | TCP_PORT_FILTERED | 端口被过滤 | 检查防火墙规则 |
| SSL错误 | TCP_SSL_ERROR | SSL/TLS握手失败 | 检查证书和协议版本 |
| DNS解析失败 | TCP_DNS_RESOLVE_FAILED | DNS解析失败 | 检查DNS配置 |

### 错误恢复策略
1. **重试机制**：可配置的重试次数，针对临时性错误
2. **降级策略**：SSL失败时尝试非SSL连接
3. **超时调整**：根据网络状况动态调整超时时间
4. **端口回退**：常用端口失败时尝试备用端口

## 性能要求

### 响应时间
| 场景 | 最大响应时间 | 说明 |
|------|--------------|------|
| 单端口探测 | 超时时间 + 500ms | 包括连接建立和数据交换 |
| 端口扫描（100端口） | 30秒 | 并行扫描，可配置并发数 |
| SSL握手 | 超时时间 + 1000ms | 证书验证和密钥交换 |

### 资源使用
| 资源 | 限制 | 说明 |
|------|------|------|
| 内存 | < 5MB/并发连接 | 包括socket缓冲区和结果存储 |
| 文件描述符 | < 1000 | 限制并发连接数 |
| 网络连接 | 可配置的最大并发数 | 避免资源耗尽 |

## 安全考虑

### 安全限制
1. **速率限制**：限制每秒连接尝试次数
2. **目标限制**：支持白名单/黑名单过滤
3. **端口范围限制**：限制可扫描的端口范围
4. **扫描深度限制**：限制扫描的并发数和频率

### 权限管理
1. **原始套接字权限**：SYN扫描需要特殊权限
2. **端口绑定权限**：源端口绑定可能需要权限
3. **网络接口访问**：特定接口访问可能需要权限

### 隐私保护
1. **日志脱敏**：不记录敏感端口和服务信息
2. **结果清理**：定期清理扫描结果
3. **访问控制**：限制扫描结果的访问权限

## 配置管理

### 配置文件
```yaml
tcp_probe:
  # 基本配置
  default_timeout_ms: 5000
  default_connect_timeout_ms: 3000
  default_read_timeout_ms: 5000
  
  # 扫描配置
  max_concurrent_connections: 10
  max_ports_per_scan: 1000
  scan_method: "connect"  # connect/syn
  
  # 端口配置
  common_ports: [21, 22, 23, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995, 3306, 3389, 5432, 8080]
  restricted_ports: []  # 禁止扫描的端口
  
  # SSL配置
  ssl_versions: ["TLSv1.2", "TLSv1.3"]
  ssl_ciphers: "HIGH:!aNULL:!MD5"
  ssl_verify: true
  
  # 安全配置
  rate_limit_per_second: 50
  enable_target_validation: true
  allowed_targets: []  # 空列表表示允许所有
  
  # 平台特定配置
  windows:
    use_raw_socket: false  # Windows默认不支持原始套接字
    
  linux:
    use_raw_socket: true
    capability_required: true  # CAP_NET_RAW
    
  macos:
    use_raw_socket: true
    sudo_required: true
```

### 环境变量
| 变量名 | 用途 | 默认值 |
|--------|------|--------|
| SDWAN_TCP_MAX_CONCURRENT | 最大并发连接数 | 10 |
| SDWAN_TCP_DEFAULT_TIMEOUT | 默认超时（秒） | 5 |
| SDWAN_TCP_SCAN_METHOD | 扫描方法 | connect |
| SDWAN_TCP_RATE_LIMIT | 速率限制（连接/秒） | 50 |
| SDWAN_TCP_SSL_VERIFY | SSL证书验证 | true |

## 测试要求

### 单元测试
1. **连接测试**：测试正常连接和错误连接
2. **超时测试**：测试各种超时场景
3. **SSL测试**：测试SSL/TLS连接和证书验证
4. **端口扫描测试**：测试端口扫描功能
5. **并发测试**：测试并发连接的性能和稳定性

### 集成测试
1. **网络测试**：在实际网络环境中测试
2. **服务识别测试**：测试常见服务的识别能力
3. **防火墙测试**：测试防火墙规则下的行为
4. **负载测试**：测试高并发下的性能表现

### 性能测试
1. **连接延迟**：测量连接建立时间
2. **吞吐测试**：测试数据传输性能
3. **并发测试**：测试并发连接的处理能力
4. **资源测试**：监控内存和文件描述符使用情况

## 监控与日志

### 日志记录
```python
# 日志格式示例
{
    "timestamp": "2024-01-20T10:30:00Z",
    "level": "INFO",
    "trace_id": "trace-123",
    "probe_id": "probe-456",
    "event": "tcp_probe_started