# ICMP探测规范

## 概述
本规范定义SD-WAN诊断平台的ICMP探测（Ping）功能，包括协议标准、实现要求、数据模型和错误处理。

## 协议标准

### ICMP协议版本
- **ICMPv4**：IPv4网络的标准ICMP协议
- **ICMPv6**：IPv6网络的标准ICMP协议

### 支持的ICMP消息类型
| 消息类型 | 类型值 | 用途 |
|----------|--------|------|
| Echo Request | 8 (ICMPv4) / 128 (ICMPv6) | 发送探测请求 |
| Echo Reply | 0 (ICMPv4) / 129 (ICMPv6) | 接收探测响应 |
| Destination Unreachable | 3 (ICMPv4) / 1 (ICMPv6) | 目标不可达 |
| Time Exceeded | 11 (ICMPv4) / 3 (ICMPv6) | TTL超时 |

## 探测参数

### 基本参数
```python
@dataclass
class IcmpProbeParameters:
    """ICMP探测参数"""
    # 目标信息
    target_host: str                    # 目标主机（IP或域名）
    target_ip: Optional[str] = None     # 解析后的IP地址
    
    # 探测配置
    count: int = 4                      # 发送次数（默认4次）
    interval_ms: int = 1000             # 发送间隔（毫秒）
    timeout_ms: int = 3000              # 超时时间（毫秒）
    ttl: Optional[int] = None           # TTL值（可选）
    
    # 数据包配置
    packet_size: int = 56               # 数据包大小（字节）
    dont_fragment: bool = False         # 是否设置DF标志
    
    # 高级配置
    source_ip: Optional[str] = None     # 源IP地址（可选）
    source_interface: Optional[str] = None  # 源接口（可选）
    ip_version: str = "auto"            # IP版本：auto/ipv4/ipv6
```

### 参数约束
1. **count**：1-100次，默认4次
2. **interval_ms**：100-10000毫秒，默认1000毫秒
3. **timeout_ms**：100-30000毫秒，默认3000毫秒
4. **packet_size**：0-65507字节（IPv4），0-65527字节（IPv6）
5. **ttl**：1-255，默认使用系统默认值

## 数据模型

### 探测结果
```python
@dataclass
class IcmpProbeResult:
    """ICMP探测结果"""
    # 基本信息
    probe_id: str                       # 探测ID
    trace_id: str                       # 追踪ID
    timestamp: datetime                 # 探测时间
    
    # 目标信息
    target_host: str                    # 目标主机
    target_ip: str                      # 目标IP地址
    resolved_ips: List[str]             # 解析的所有IP地址
    
    # 统计信息
    packets_sent: int                   # 发送包数
    packets_received: int               # 接收包数
    packet_loss_rate: float             # 丢包率（0-1）
    
    # 延迟统计（单位：毫秒）
    min_rtt: Optional[float]            # 最小RTT
    avg_rtt: Optional[float]            # 平均RTT
    max_rtt: Optional[float]            # 最大RTT
    stddev_rtt: Optional[float]         # RTT标准差
    jitter: Optional[float]             # 抖动（RTT变化）
    
    # 详细结果
    packet_results: List[IcmpPacketResult]  # 每个包的结果
    
    # 状态信息
    success: bool                       # 是否成功
    error_message: Optional[str]        # 错误信息
    error_code: Optional[str]           # 错误代码
    
    # 性能指标
    probe_duration_ms: float            # 探测总耗时
    dns_resolution_ms: Optional[float]  # DNS解析耗时
```

### 单个包结果
```python
@dataclass
class IcmpPacketResult:
    """单个ICMP包结果"""
    # 包信息
    sequence_number: int                # 序列号
    packet_size: int                    # 包大小
    
    # 时间信息
    send_time: datetime                 # 发送时间
    receive_time: Optional[datetime]    # 接收时间（如果成功）
    rtt_ms: Optional[float]             # RTT（毫秒）
    
    # 网络信息
    ttl: Optional[int]                  # 接收到的TTL
    source_ip: Optional[str]            # 源IP地址
    destination_ip: Optional[str]       # 目标IP地址
    
    # 状态
    success: bool                       # 是否成功
    timeout: bool                       # 是否超时
    error_message: Optional[str]        # 错误信息
```

## 实现要求

### 平台兼容性
| 平台 | 实现方式 | 备注 |
|------|----------|------|
| Windows | 使用 `pythonping` 库或原生 `ping` 命令 | 需要管理员权限发送原始套接字 |
| Linux | 使用 `pythonping` 库或原生 `ping` 命令 | 需要CAP_NET_RAW权限 |
| macOS | 使用 `pythonping` 库或原生 `ping` 命令 | 需要权限配置 |

### 实现策略
1. **优先使用库实现**：优先使用 `pythonping` 等跨平台库
2. **备选系统命令**：库不可用时使用系统 `ping` 命令并解析输出
3. **异步支持**：支持异步执行多个探测
4. **资源管理**：限制并发探测数量，避免资源耗尽

### 代码示例
```python
@tool_function(
    name="icmp_ping",
    description="ICMP连通性探测",
    timeout=30,
    retry_count=2
)
class IcmpPingTool:
    """ICMP Ping工具"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.max_concurrent = self.config.get("max_concurrent", 10)
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
    
    async def execute(self, request: ToolRequest, ctx: Context) -> ToolResponse:
        """执行ICMP探测"""
        # 参数验证
        params = self._validate_parameters(request.parameters)
        
        # 解析目标
        resolved_ips = await self._resolve_target(params.target_host)
        
        # 执行探测
        results = []
        async with self.semaphore:
            for ip in resolved_ips:
                result = await self._ping_single_ip(ip, params)
                results.append(result)
        
        # 合并结果
        final_result = self._merge_results(results, params)
        
        return ToolResponse(
            success=True,
            data=final_result.to_dict(),
            trace_id=ctx.trace_id
        )
    
    async def _ping_single_ip(self, ip: str, params: IcmpProbeParameters) -> IcmpProbeResult:
        """探测单个IP地址"""
        # 实现具体的ping逻辑
        pass
```

## 错误处理

### 错误分类
| 错误类型 | 错误代码 | 描述 | 处理建议 |
|----------|----------|------|----------|
| 解析失败 | ICMP_RESOLVE_FAILED | DNS解析失败 | 检查DNS配置，尝试直接使用IP |
| 权限不足 | ICMP_PERMISSION_DENIED | 缺少发送原始套接字权限 | 使用系统ping命令或提升权限 |
| 目标不可达 | ICMP_DEST_UNREACHABLE | 目标主机不可达 | 检查网络连接和路由 |
| 超时 | ICMP_TIMEOUT | 探测超时 | 增加超时时间或检查防火墙 |
| TTL超时 | ICMP_TTL_EXCEEDED | TTL过期 | 检查路由环路或增加TTL |

### 错误恢复策略
1. **重试机制**：可配置的重试次数和退避策略
2. **降级策略**：库失败时降级到系统命令
3. **超时处理**：支持可配置的超时时间
4. **资源清理**：确保资源正确释放

## 性能要求

### 响应时间
| 指标 | 要求 | 备注 |
|------|------|------|
| 单次探测 | < 超时时间 + 100ms | 包括网络延迟和处理时间 |
| 并发探测 | 线性增长，不超过资源限制 | 使用信号量控制并发 |
| DNS解析 | < 2000ms | 可配置超时 |

### 资源使用
| 资源 | 限制 | 备注 |
|------|------|------|
| 内存 | < 10MB/并发探测 | 包括缓冲区和结果存储 |
| CPU | < 10%/并发探测 | 避免CPU密集型操作 |
| 网络 | 可配置的包大小和频率 | 避免网络拥塞 |

## 安全考虑

### 安全限制
1. **速率限制**：限制每秒发送的ICMP包数量
2. **目标限制**：支持白名单/黑名单过滤
3. **包大小限制**：限制最大包大小，避免放大攻击
4. **源地址验证**：防止IP欺骗

### 权限管理
1. **最小权限**：使用最低必要权限执行探测
2. **权限检查**：执行前检查所需权限
3. **权限提升**：仅在必要时请求提升权限
4. **权限记录**：记录权限使用情况

## 配置管理

### 配置文件
```yaml
icmp_probe:
  # 基本配置
  default_count: 4
  default_timeout_ms: 3000
  default_interval_ms: 1000
  default_packet_size: 56
  
  # 高级配置
  max_concurrent: 10
  max_packet_size: 1500
  min_interval_ms: 100
  max_ttl: 255
  
  # 安全配置
  rate_limit_per_second: 100
  enable_source_validation: true
  allowed_targets: []  # 空列表表示允许所有
  
  # 平台特定配置
  windows:
    use_raw_socket: false  # Windows默认使用系统命令
    admin_required: true
    
  linux:
    use_raw_socket: true
    capability_required: true
    
  macos:
    use_raw_socket: false
    sudo_required: true
```

### 环境变量
| 变量名 | 用途 | 默认值 |
|--------|------|--------|
| SDWAN_ICMP_MAX_CONCURRENT | 最大并发数 | 10 |
| SDWAN_ICMP_DEFAULT_TIMEOUT | 默认超时（秒） | 3 |
| SDWAN_ICMP_USE_RAW_SOCKET | 是否使用原始套接字 | auto |
| SDWAN_ICMP_RATE_LIMIT | 速率限制（包/秒） | 100 |

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
    "timestamp": "2024-01-20T10:30:00Z",
    "level": "INFO",
#### 使用系统ping命令
```python
import subprocess
import re
from typing import List

class SystemPingIcmpProbe(IcmpProbeInterface):
    """基于系统ping命令的ICMP探测实现"""
    
    def __init__(self, platform: str = "auto"):
        self.platform = platform or self._detect_platform()
        self.name = f"system_ping_{self.platform}"
        self.version = "1.0.0"
    
    def ping(self, target: str, **kwargs) -> IcmpProbeCompleteResult:
        # 构建ping命令
        cmd = self._build_ping_command(target, kwargs)
        
        try:
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=(kwargs.get('timeout_ms', 3000) / 1000) + 5
            )
            
            # 解析输出
            return self._parse_output(target, result.stdout, result.stderr, kwargs)
            
        except subprocess.TimeoutExpired:
            return self._build_error_result(target, "Command timeout", kwargs)
        except Exception as e:
            return self._build_error_result(target, str(e), kwargs)
    
    def _build_ping_command(self, target: str, params: dict) -> List[str]:
        """构建ping命令"""
        if self.platform == "windows":
            cmd = ["ping", target]
            if params.get('count'):
                cmd.extend(["-n", str(params['count'])])
            if params.get('timeout_ms'):
                cmd.extend(["-w", str(params['timeout_ms'])])
            if params.get('packet_size'):
                cmd.extend(["-l", str(params['packet_size'])])
            if params.get('ttl'):
                cmd.extend(["-i", str(params['ttl'])])
        else:  # linux/macos
            cmd = ["ping", target]
            if params.get('count'):
                cmd.extend(["-c", str(params['count'])])
            if params.get('timeout_ms'):
                cmd.extend(["-W", str(params['timeout_ms'] // 1000)])
            if params.get('packet_size'):
                cmd.extend(["-s", str(params['packet_size'])])
            if params.get('ttl'):
                cmd.extend(["-t", str(params['ttl'])])
            if params.get('interval_ms'):
                cmd.extend(["-i", str(params['interval_ms'] / 1000)])
        
        return cmd
    
    def _parse_output(self, target: str, stdout: str, stderr: str, params: dict) -> IcmpProbeCompleteResult:
        """解析ping命令输出"""
        # 平台特定的解析逻辑
        if self.platform == "windows":
            return self._parse_windows_output(target, stdout, stderr, params)
        else:
            return self._parse_unix_output(target, stdout, stderr, params)
    
    def _parse_windows_output(self, target: str, stdout: str, stderr: str, params: dict) -> IcmpProbeCompleteResult:
        """解析Windows ping输出"""
        # 实现Windows输出解析
        # 这里简化处理，实际需要完整解析
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "platform": self.platform,
            "features": ["ping", "statistics"],
            "limitations": ["requires_system_ping", "output_parsing_needed"]
        }
```

## 性能要求

### 响应时间
| 场景 | 最大响应时间 | 说明 |
|------|--------------|------|
| 单次探测 | 5秒 | 包括DNS解析时间 |
| 批量探测（10个目标） | 30秒 | 并行执行 |
| 连续探测 | 按配置间隔 | 保持稳定间隔 |

### 资源使用
| 资源 | 限制 | 说明 |
|------|------|------|
| 内存 | < 10MB | 单次探测内存占用 |
| CPU | < 5% | 单核使用率 |
| 网络带宽 | < 100Kbps | 探测流量 |

## 错误处理

### 重试策略
```python
@dataclass
class IcmpProbeRetryPolicy:
    """ICMP探测重试策略"""
    max_retries: int = 3                    # 最大重试次数
    initial_delay_ms: int = 1000            # 初始延迟
    backoff_factor: float = 2.0             # 退避因子
    max_delay_ms: int = 10000               # 最大延迟
    
    def get_delay(self, attempt: int) -> int:
        """计算重试延迟"""
        delay = self.initial_delay_ms * (self.backoff_factor ** (attempt - 1))
        return min(delay, self.max_delay_ms)
```

### 错误恢复
1. **临时故障**：自动重试
2. **永久故障**：记录错误并继续
3. **配置错误**：立即失败并报告
4. **权限错误**：提示用户并停止

## 安全考虑

### 权限要求
- **普通用户**：允许执行ping
- **管理员/root**：可能需要特殊权限

### 限制措施
1. **速率限制**：防止DoS攻击
2. **目标限制**：白名单/黑名单
3. **大小限制**：数据包大小限制
4. **频率限制**：探测频率限制

### 隐私保护
1. **日志脱敏**：不记录敏感目标
2. **结果清理**：定期清理探测结果
3. **访问控制**：限制结果访问权限

## 测试要求

### 单元测试
```python
def test_icmp_probe_basic():
    """测试基本ICMP探测功能"""
    probe = PythonPingIcmpProbe()
    result = probe.ping("127.0.0.1", count=2)
    
    assert result.overall_success is True
    assert result.statistics.packets_sent == 2
    assert 0 <= result.statistics.packet_loss_rate <= 1

def test_icmp_probe_timeout():
    """测试超时场景"""
    probe = PythonPingIcmpProbe()
    result = probe.ping("192.0.2.1", count=1, timeout_ms=100)  # 测试地址
    
    assert result.overall_success is False
    assert result.statistics.packet_loss_rate == 1.0
```

### 集成测试
1. **网络连通