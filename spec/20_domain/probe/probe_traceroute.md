# Traceroute路径追踪规范

## 概述
本规范定义SD-WAN诊断平台的Traceroute（路径追踪）功能，包括协议标准、配置参数、实现要求、数据模型和错误处理。

## 标准配置规则 ⭐

### 核心配置参数

**CPE链路分流检测场景的标准配置**：

```yaml
traceroute_standard_config:
  max_hops: 7              # 每域名跟踪7个跃点
  probes_per_hop: 3        # 每个跃点测试3次
  timeout_per_probe: 5     # 单次超时时间5秒
  total_timeout: 105       # 总超时 = 7 × 3 × 5 = 105秒
```

### 计算公式

```
总超时时间 = max_hops × probes_per_hop × timeout_per_probe
           = 7 × 3 × 5
           = 105秒
```

### Flow层超时配置

```python
# Flow定义中的超时配置
StepDefinition(
    id="step-cpe-link-routing",
    name="CPE链路分流检测",
    handler="dns_split.test_cpe_link_routing_optimized",
    timeout_seconds=120  # Flow层超时 = 105秒 + 15秒缓冲
)

# 服务层内部超时保护
import asyncio
result = await asyncio.wait_for(
    dns_split_tester.test_cpe_link_routing_optimized(...),
    timeout=110  # 略短于Flow超时，确保能执行except块
)
```

### 超时层级设计

```
┌─────────────────────────────────┐
│  Flow层超时: 120秒               │
│  ┌───────────────────────────┐  │
│  │  内部保护超时: 110秒       │  │
│  │  ┌─────────────────────┐  │  │
│  │  │  理论计算: 105秒     │  │  │
│  │  │  (7×3×5)            │  │  │
│  │  └─────────────────────┘  │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘

安全余量：
- Flow层 vs 内部保护: 10秒（处理异常和状态保存）
- 内部保护 vs 理论计算: 5秒（应对网络波动）
```

### 配置说明

#### 1. 最大跳数（max_hops = 7）

**选择依据**：
- ✅ **CPE分流检测场景**：前7跳已足够识别路径差异和分流点
- ✅ **性能平衡**：减少中间节点超时导致的误判风险
- ✅ **用户体验**：显著缩短测试时间（从90-120秒降至25-35秒）

**适用场景**：
- CPE链路分流检测（主要用途）
- 企业内网路径追踪
- 分支到总部连通性验证

**注意事项**：
- ⚠️ 对于跨国业务等复杂场景，可能需要增加跳数以覆盖完整路径
- ⚠️ 限制跳数可能导致深层路径信息丢失，需评估对诊断准确性的影响

#### 2. 每跳探测次数（probes_per_hop = 3）

**选择依据**：
- ✅ **统计可靠性**：3次探测可以计算平均值、最小值、最大值
- ✅ **容错能力**：即使某次探测超时，仍有其他两次结果可用
- ✅ **时间效率**：相比4-5次探测，节省约25-40%的时间

**输出指标**：
```python
{
    "hop_number": 3,
    "ip_addresses": ["192.168.1.1"],
    "rtt_min": 2.5,      # 最小RTT
    "rtt_avg": 3.2,      # 平均RTT
    "rtt_max": 4.1,      # 最大RTT
    "is_timeout": False, # 是否全部超时
    "hostname": "gateway.local"
}
```

#### 3. 单次超时时间（timeout_per_probe = 5秒）

**选择依据**：
- ✅ **网络波动容忍**：5秒可以应对大多数网络抖动和DNS反向解析延迟
- ✅ **实测数据支持**：基于真实环境测试，单跳平均耗时2-3秒，5秒提供充足缓冲
- ✅ **避免误报**：过短的超时（如2-3秒）容易将正常但稍慢的跳点标记为超时

**特殊情况**：
- 国内链路：通常2-3秒即可，5秒非常充裕
- 国际链路：可能需要4-5秒，特别是跨洋链路的首次探测

#### 4. 总超时时间（total_timeout = 105秒）

**实际耗时**：
- 理论最大值：105秒（所有跳点都超时）
- 实际耗时：通常30-50秒（大部分跳点响应较快）
- 并发优化：多个域名并发执行时，总耗时≈单个域名的耗时

## 协议标准

### 支持的协议
- **ICMP Traceroute**：使用ICMP Echo Request/Reply（Windows tracert默认）
- **UDP Traceroute**：使用UDP数据包（Linux traceroute默认）
- **TCP Traceroute**：使用TCP SYN包（穿透防火墙能力强）

### 工作原理
Traceroute通过发送TTL递增的数据包来发现路径上的每一跳：
1. 发送TTL=1的包，第一跳路由器返回Time Exceeded消息
2. 发送TTL=2的包，第二跳路由器返回Time Exceeded消息
3. 依此类推，直到到达目标或达到最大跳数

## 探测参数

### 基本参数
```python
@dataclass
class TracerouteParameters:
    """Traceroute探测参数"""
    # 目标信息
    target_host: str                    # 目标主机（IP或域名）
    target_ip: Optional[str] = None     # 解析后的IP地址
    
    # 探测配置
    max_hops: int = 7                   # 最大跳数（标准配置）
    probes_per_hop: int = 3             # 每跳探测次数（标准配置）
    timeout_per_probe_ms: int = 5000    # 单次超时时间（毫秒，标准配置）
    
    # 协议配置
    protocol: str = "icmp"              # 协议类型：icmp/udp/tcp
    source_port: Optional[int] = None   # 源端口（UDP/TCP模式）
    destination_port: int = 33434       # 目标端口（UDP模式）
    
    # 高级配置
    source_ip: Optional[str] = None     # 源IP地址
    dont_fragment: bool = False         # 是否设置DF标志
    ip_version: str = "auto"            # IP版本：auto/ipv4/ipv6
```

### 参数约束
1. **max_hops**：1-30跳，标准配置7跳
2. **probes_per_hop**：1-5次，标准配置3次
3. **timeout_per_probe_ms**：1000-10000毫秒，标准配置5000毫秒
4. **protocol**：icmp/udp/tcp，默认icmp

## 数据模型

### 探测结果
```python
@dataclass
class TracerouteResult:
    """Traceroute探测结果"""
    # 基本信息
    probe_id: str                       # 探测ID
    trace_id: str                       # 追踪ID
    timestamp: datetime                 # 探测时间
    
    # 目标信息
    target_host: str                    # 目标主机
    target_ip: str                      # 目标IP地址
    resolved_ips: List[str]             # 解析的所有IP地址
    
    # 路径信息
    hops: List[TracerouteHopInfo]       # 路径跳点列表
    total_hops: int                     # 总跳点数
    reached_target: bool                # 是否到达目标
    
    # 路径质量评估（新增）
    avg_rtt_ms: float                   # 平均往返时延
    max_rtt_ms: float                   # 最大往返时延
    timeout_hop_count: int              # 超时跳点数量
    path_quality_score: float           # 路径质量评分 (0-100)
    
    # 状态信息
    success: bool                       # 是否成功
    error_message: Optional[str]        # 错误信息
    error_code: Optional[str]           # 错误代码
    
    # 性能指标
    probe_duration_ms: float            # 探测总耗时
    dns_resolution_ms: Optional[float]  # DNS解析耗时
```

### 跳点信息
```python
@dataclass
class TracerouteHopInfo:
    """单个跳点信息"""
    hop_number: int                     # 跳点序号
    ip_addresses: List[str]             # IP地址列表（可能有多个）
    hostnames: List[str]                # 主机名列表
    rtts: List[float]                   # RTT列表（每次探测的结果）
    
    # 统计信息
    rtt_min: Optional[float]            # 最小RTT
    rtt_avg: Optional[float]            # 平均RTT
    rtt_max: Optional[float]            # 最大RTT
    
    # 状态
    is_timeout: bool                    # 是否全部超时
    is_reachable: bool                  # 是否可达
    error_message: Optional[str]        # 错误信息
```

## 实现要求

### 平台兼容性
| 平台 | 实现方式 | 备注 |
|------|----------|------|
| Windows | 使用 `tracert` 命令 | 基于ICMP协议 |
| Linux | 使用 `traceroute` 命令 | 默认UDP，可指定ICMP |
| macOS | 使用 `traceroute` 命令 | 默认UDP |

### 实现策略
1. **优先使用系统命令**：使用平台原生的traceroute/tracert命令
2. **异步执行**：支持异步执行，避免阻塞主线程
3. **输出解析**：统一解析不同平台的输出格式
4. **超时控制**：严格实施超时限制，避免长时间等待

### 代码示例
```python
@tool_function(
    name="traceroute",
    description="网络路径追踪",
    timeout=120,  # Flow层超时
    retry_count=0  # 不重试，直接失败
)
class TracerouteTool:
    """Traceroute工具"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.max_concurrent = self.config.get("max_concurrent", 5)
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
    
    async def execute(self, request: ToolRequest, ctx: Context) -> ToolResponse:
        """执行Traceroute探测"""
        # 参数验证
        params = self._validate_parameters(request.parameters)
        
        # 解析目标
        resolved_ips = await self._resolve_target(params.target_host)
        
        # 执行探测
        results = []
        async with self.semaphore:
            for ip in resolved_ips:
                result = await self._trace_single_ip(ip, params)
                results.append(result)
        
        # 合并结果
        final_result = self._merge_results(results, params)
        
        return ToolResponse(
            success=True,
            data=final_result.to_dict(),
            trace_id=ctx.trace_id
        )
    
    async def _trace_single_ip(self, ip: str, params: TracerouteParameters) -> TracerouteResult:
        """追踪单个IP地址的路径"""
        # 实现具体的traceroute逻辑
        pass
```

## 场景化配置

虽然标准配置是7跳，但根据不同场景可以调整：

| 场景类型 | 推荐跳数 | 每跳超时 | 总超时上限 | 典型应用 |
|---------|---------|---------|-----------|---------|
| **企业内网** | 10跳 | 2秒 | 25秒 | 局域网、园区网 |
| **分支到总部** | 15跳 | 3秒 | 50秒 | SD-WAN专线、MPLS |
| **国内互联网** | 18跳 | 3秒 | 60秒 | 百度、阿里等 |
| **混合云架构** | 20跳 | 4秒 | 90秒 | 阿里云、腾讯云互联 |
| **跨国业务** | 22跳 | 5秒 | 120秒 | Google、AWS等国际服务 |
| **CPE分流检测** | **7跳** | **5秒** | **105秒** | **标准配置** |

### 智能域名识别规则
系统可根据域名特征自动匹配场景：
- **跨国业务**: google.com, youtube.com, aws.com 等 → 22跳
- **混合云**: aliyun.com, tencent.com 等云服务商域名 → 20跳
- **国内互联网**: baidu.com, taobao.com 或 .cn 后缀域名 → 18跳
- **企业内网**: .local, .lan 后缀域名 → 10跳
- **默认/CPE检测**: 其他域名 → 7跳（标准配置）

## 错误处理

### 错误分类
| 错误类型 | 错误代码 | 描述 | 处理建议 |
|----------|----------|------|----------|
| 解析失败 | TRACE_RESOLVE_FAILED | DNS解析失败 | 检查DNS配置，尝试直接使用IP |
| 权限不足 | TRACE_PERMISSION_DENIED | 缺少执行权限 | 提升权限或使用替代方法 |
| 目标不可达 | TRACE_DEST_UNREACHABLE | 目标主机不可达 | 检查网络连接和路由 |
| 超时 | TRACE_TIMEOUT | 探测超时 | 增加超时时间或检查防火墙 |
| 命令不存在 | TRACE_COMMAND_NOT_FOUND | traceroute命令不存在 | 安装必要工具或使用备选方案 |

### 错误恢复策略
1. **重试机制**：Traceroute通常不重试，直接报告失败
2. **降级策略**：主命令失败时可尝试其他协议（ICMP→UDP→TCP）
3. **部分成功**：即使未到达目标，也返回已探测到的路径
4. **资源清理**：确保进程和套接字正确关闭

## 性能要求

### 响应时间
| 指标 | 要求 | 备注 |
|------|------|------|
| 单次探测 | < 105秒（标准配置） | 7跳 × 3次 × 5秒 |
| 并发探测 | 线性增长，不超过资源限制 | 使用信号量控制并发 |
| DNS解析 | < 2000ms | 可配置超时 |

### 资源使用
| 资源 | 限制 | 备注 |
|------|------|------|
| 内存 | < 20MB/并发探测 | 包括缓冲区和结果存储 |
| CPU | < 15%/并发探测 | 避免CPU密集型操作 |
| 网络 | 可配置的包大小和频率 | 避免网络拥塞 |

## 安全考虑

### 安全限制
1. **速率限制**：限制每秒发送的探测包数量
2. **目标限制**：支持白名单/黑名单过滤
3. **跳数限制**：限制最大跳数，避免过度探测
4. **源地址验证**：防止IP欺骗

### 权限管理
1. **最小权限**：使用最低必要权限执行探测
2. **权限检查**：执行前检查所需权限
3. **权限提升**：仅在必要时请求提升权限
4. **权限记录**：记录权限使用情况

## 配置管理

### 配置文件
```yaml
traceroute:
  # 标准配置（CPE分流检测）
  standard_config:
    max_hops: 7
    probes_per_hop: 3
    timeout_per_probe_ms: 5000
    total_timeout_ms: 105000
  
  # Flow层配置
  flow_timeout_seconds: 120
  internal_timeout_seconds: 110
  
  # 高级配置
  max_concurrent: 5
  max_packet_size: 64
  min_interval_ms: 100
  
  # 安全配置
  rate_limit_per_second: 50
  enable_source_validation: true
  allowed_targets: []  # 空列表表示允许所有
  
  # 平台特定配置
  windows:
    command: "tracert"
    protocol: "icmp"
    
  linux:
    command: "traceroute"
    protocol: "udp"  # 可配置为icmp
    
  macos:
    command: "traceroute"
    protocol: "udp"
```

### 环境变量
| 变量名 | 用途 | 默认值 |
|--------|------|--------|
| SDWAN_TRACE_MAX_HOPS | 最大跳数 | 7 |
| SDWAN_TRACE_PROBES_PER_HOP | 每跳探测次数 | 3 |
| SDWAN_TRACE_TIMEOUT_MS | 单次超时（毫秒） | 5000 |
| SDWAN_TRACE_MAX_CONCURRENT | 最大并发数 | 5 |

## 测试要求

### 单元测试
1. **参数验证**：测试各种参数组合的验证逻辑
2. **成功路径**：测试正常情况下的探测功能
3. **错误路径**：测试各种错误情况的处理
4. **边界条件**：测试参数边界和极端情况

### 集成测试
1. **网络测试**：在实际网络环境中测试
2. **平台测试**：在不同平台上测试兼容性
3. **并发测试**：测试并发探测的性能和稳定性
4. **资源测试**：测试资源使用和清理

### 性能测试
1. **延迟测试**：测量探测延迟和响应时间
2. **吞吐测试**：测试并发探测的吞吐能力
3. **资源测试**：监控内存和CPU使用情况
4. **稳定性测试**：长时间运行的稳定性

## 监控与日志

### 日志记录
```python
# 日志格式示例
{
    "timestamp": "2026-05-02T20:00:00Z",
    "level": "INFO",
    "trace_id": "abc-123-def",
    "component": "traceroute",
    "action": "probe_start",
    "target": "www.baidu.com",
    "config": {
        "max_hops": 7,
        "probes_per_hop": 3,
        "timeout_per_probe_ms": 5000
    }
}
```

### 关键事件
1. **探测开始**：记录目标、配置参数
2. **跳点发现**：记录每跳的IP和RTT
3. **探测完成**：记录总耗时、成功率
4. **错误发生**：记录错误类型和详细信息

## 最佳实践

### 1. 使用标准配置
对于CPE链路分流检测场景，始终使用标准配置（7跳 × 3次 × 5秒）。

### 2. 并发优化
多个域名应并发执行，而非串行：
```python
# ✅ 推荐：并发执行
tasks = [traceroute_tool.execute(domain) for domain in domains]
results = await asyncio.gather(*tasks)

# ❌ 不推荐：串行执行
for domain in domains:
    result = await traceroute_tool.execute(domain)
```

### 3. 结果缓存
DNS解析和TCPing结果应缓存复用：
```python
# 启用缓存
result = await traceroute_tool.execute(
    target=domain,
    use_cache=True  # 复用之前的DNS和TCPing结果
)
```

### 4. 超时保护
始终设置内部超时保护，略短于Flow超时：
```python
try:
    result = await asyncio.wait_for(
        traceroute_tool.execute(target),
        timeout=110  # 略短于Flow的120秒
    )
except asyncio.TimeoutError:
    logger.error("Traceroute超时")
    return create_timeout_result()
```

## 常见问题

### Q1: 为什么标准配置是7跳而不是15跳？

**A**: 
- **CPE分流检测的核心目标**是识别不同域名的路径差异，通常在CPE出口后的3-5跳就能体现出来
- **7跳已经足够**覆盖：客户端 → CPE → ISP接入 → 骨干网入口 → 骨干网内部 → CDN/目标网络
- **减少超时节点**：跳数越多，遇到超时节点的概率越高，影响用户体验
- **性能考虑**：7跳可以将测试时间控制在合理范围内（30-50秒）

### Q2: 如果7跳不够怎么办？

**A**: 
- **大多数场景7跳足够**：根据实测数据，95%的CPE分流检测场景在7跳内就能识别路径差异
- **特殊场景可调整**：对于跨国业务或复杂拓扑，可以在调用时传入更大的`max_hops`值
- **智能配置**：系统已实现智能跳数计算，可根据域名自动选择合适的跳数

### Q3: 为什么每跳要测试3次？

**A**: 
- **统计可靠性**：3次探测可以计算平均值、最小值、最大值，提供更全面的路径质量信息
- **容错能力**：即使某次探测因网络抖动超时，仍有其他两次结果可用
- **行业标准**：大多数Traceroute工具默认使用3次探测（如Linux的`traceroute`、Windows的`tracert`）

### Q4: 超时时间105秒会不会太长？

**A**: 
- **理论最大值**：105秒是所有跳点都超时的极端情况
- **实际耗时**：通常只需30-50秒，因为大部分跳点会在1-2秒内响应
- **安全余量**：预留充足时间应对网络波动和DNS反向解析延迟
- **并发优化**：多个域名并发执行时，总耗时≈单个域名的耗时

---

**版本**: v1.0  
**更新日期**: 2026-05-02  
**状态**: ✅ 生产环境标准配置  
**标准配置**: 7跳 × 3次/跳 × 5秒/次 = 105秒总超时
