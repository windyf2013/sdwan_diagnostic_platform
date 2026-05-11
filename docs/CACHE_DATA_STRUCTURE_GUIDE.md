# 缓存数据结构设计指南

## 📋 问题背景

在 SD-WAN 诊断平台的 Flow 执行过程中，不同步骤之间需要共享探测结果（如 DNS 解析、TCPing、Traceroute），以避免重复执行耗时操作。

**核心问题**：应该使用 **字典格式** 还是 **Dataclass 格式** 来存储这些缓存数据？

---

## 🎯 最终方案：混合模式

### 设计理念

```
┌─────────────────────────────────────────────┐
│         内部处理层（类型安全）                │
│   ┌───────────────────────────────────┐    │
│   │  Dataclass 对象                     │    │
│   │  - IDE 自动补全                    │    │
│   │  - 静态类型检查                    │    │
│   │  - 方法扩展能力                    │    │
│   └───────────────────────────────────┘    │
│              ↓ to_dict()                     │
├─────────────────────────────────────────────┤
│         Context 存储层（兼容性）             │
│   ┌───────────────────────────────────┐    │
│   │  Dict[str, dict]                   │    │
│   │  - JSON 序列化友好                 │    │
│   │  - 跨模块传递简单                  │    │
│   │  - 向后兼容性强                    │    │
│   └───────────────────────────────────┘    │
│              ↓ from_dict()                   │
├─────────────────────────────────────────────┤
│         读取使用层（类型安全）               │
│   ┌───────────────────────────────────┐    │
│   │  Dataclass 对象                     │    │
│   │  - 享受完整的类型提示              │    │
│   │  - 防错性验证                      │    │
│   └───────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## 📦 已实现的缓存数据类

### 1. DnsResolutionEntry（DNS 解析缓存）

**位置**：[`dns_split.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py) 第 18-52 行

```python
@dataclass(slots=True)
class DnsResolutionEntry:
    """DNS解析缓存条目"""
    domain: str
    domestic_ips: List[str] = field(default_factory=list)
    international_ips: List[str] = field(default_factory=list)
    is_split: bool = False
    query_time_ms: float = 0.0
    
    def to_dict(self) -> dict:
        """转换为字典（用于序列化到 Context）"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DnsResolutionEntry':
        """从字典恢复（用于从 Context 读取）"""
        return cls(**data)
    
    def validate(self) -> bool:
        """验证数据完整性"""
        return bool(
            self.domain and 
            (self.domestic_ips or self.international_ips)
        )
    
    def get_all_ips(self) -> List[str]:
        """获取所有解析到的IP（去重）"""
        return list(set(self.domestic_ips + self.international_ips))
```

**使用示例**：

```python
# ✅ 写入缓存（在 test_optimized 方法中）
entry = DnsResolutionEntry(
    domain="www.baidu.com",
    domestic_ips=["39.156.70.46", "39.156.70.239"],
    international_ips=["39.156.70.46"],
    is_split=True,
    query_time_ms=850.5
)

# 存入 Context 时转换为字典
ctx.set("dns_resolution_cache", {
    "www.baidu.com": entry.to_dict()
})

# ✅ 读取缓存（在后续步骤中）
dns_cache_dict = ctx.get("dns_resolution_cache")
if dns_cache_dict:
    # 恢复为 Dataclass，享受类型安全
    baidu_entry = DnsResolutionEntry.from_dict(dns_cache_dict["www.baidu.com"])
    
    # IDE 自动补全 + 类型检查
    if baidu_entry.validate():
        print(f"Baidu IPs: {baidu_entry.get_all_ips()}")
        print(f"Is split: {baidu_entry.is_split}")
```

---

### 2. TcpingResultEntry（TCPing 结果缓存）

```python
@dataclass(slots=True)
class TcpingResultEntry:
    """TCPing结果缓存条目"""
    target: str
    is_reachable: bool = False
    avg_response_time_ms: float = 0.0
    packet_loss_rate: float = 0.0
    probe_time_ms: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TcpingResultEntry':
        return cls(**data)
```

---

### 3. TracerouteResultEntry（Traceroute 结果缓存）

```python
@dataclass(slots=True)
class TracerouteResultEntry:
    """Traceroute结果缓存条目"""
    domain: str
    resolved_ip: str = ""
    ip_version: str = "unknown"
    full_path: List[dict] = field(default_factory=list)
    path_fingerprint: str = ""
    link_category: str = "unknown"
    confidence: float = 0.0
    duration_ms: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TracerouteResultEntry':
        return cls(**data)
    
    def get_hop_count(self) -> int:
        """获取跳点数"""
        return len(self.full_path)
    
    def has_valid_path(self) -> bool:
        """验证是否有有效路径"""
        return bool(self.resolved_ip and self.full_path)
```

---

## 🔧 实现细节

### 为什么使用 `slots=True`？

```python
@dataclass(slots=True)
class MyDataClass:
    ...
```

**优势**：
- ✅ **内存优化**：减少约 40-50% 的内存占用（对于大量缓存条目很重要）
- ✅ **性能提升**：属性访问速度更快
- ✅ **防止动态添加属性**：增强数据结构的稳定性

**注意**：Python 3.10+ 才支持 `slots=True`

---

### 序列化策略

#### 写入 Context（Dataclass → Dict）

```python
# 方法 1：使用 dataclasses.asdict()（推荐）
from dataclasses import asdict

ctx.set("cache", {
    "key": my_entry.to_dict()  # to_dict() 内部调用 asdict(self)
})

# 方法 2：手动转换（适用于复杂嵌套结构）
ctx.set("cache", {
    "key": {
        "field1": my_entry.field1,
        "field2": my_entry.field2.to_dict(),  # 嵌套对象
    }
})
```

#### 读取 Context（Dict → Dataclass）

```python
# 方法 1：使用 from_dict() 类方法（推荐）
cache_dict = ctx.get("cache")
my_entry = MyDataClass.from_dict(cache_dict["key"])

# 方法 2：直接解包（简单场景）
my_entry = MyDataClass(**cache_dict["key"])
```

---

## 📊 性能对比

| 指标 | 纯字典 | 纯 Dataclass | 混合模式（推荐） |
|------|-------|-------------|----------------|
| **内存占用** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐（slots优化） |
| **类型安全** | ❌ | ✅✅✅ | ✅✅✅ |
| **IDE 支持** | ❌ | ✅✅✅ | ✅✅✅ |
| **序列化复杂度** | ⭐ | ⭐⭐ | ⭐⭐ |
| **灵活性** | ✅✅✅ | ⭐⭐ | ✅✅ |
| **重构友好度** | ❌ | ✅✅✅ | ✅✅✅ |

---

## 💡 最佳实践

### 1. 何时使用 Dataclass？

✅ **推荐使用**：
- 数据结构固定且明确
- 需要在多个模块间传递
- 需要类型安全和 IDE 支持
- 需要添加辅助方法（如 [validate()](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\collector\base.py#L76-L85), [to_dict()](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\core\errors\base.py#L28-L35)）

❌ **不推荐使用**：
- 数据结构频繁变化
- 只需要临时存储（不涉及跨模块传递）
- 性能极度敏感的场景（微秒级优化）

### 2. 何时使用字典？

✅ **推荐使用**：
- 动态键值对（键名不确定）
- 简单的配置数据
- 与外部 API 交互（JSON 格式）

❌ **不推荐使用**：
- 复杂的嵌套结构
- 需要类型安全的场景
- 长期维护的核心数据结构

### 3. 混合模式的使用原则

```python
# ✅ 正确做法：内部使用 Dataclass，Context 存储字典
class MyService:
    async def process(self, ctx: FlowContext):
        # 1. 内部处理：使用 Dataclass
        result = MyDataClass(field1="value1", field2=123)
        
        # 2. 存入 Context：转换为字典
        ctx.set("result", result.to_dict())
        
        # 3. 其他步骤读取：恢复为 Dataclass
        cached = ctx.get("result")
        restored = MyDataClass.from_dict(cached)
        
        # 4. 享受类型安全
        print(restored.field1)  # IDE 自动补全
```

```python
# ❌ 错误做法：直接在 Context 中存储 Dataclass 对象
ctx.set("result", my_dataclass_instance)  # 可能导致序列化问题
```

---

## 🚀 实际应用示例

### 场景：DNS 解析结果复用

```python
# 步骤 1: DNS 分流测试（写入缓存）
async def step_dns_split(ctx: FlowContext):
    result = await dns_split_tester.test_optimized(
        domains=["www.baidu.com", "www.google.com"],
        ctx=ctx
    )
    # ✅ test_optimized 内部已将结果转换为 DnsResolutionEntry
    #    并存入 ctx.set("dns_resolution_cache", {...})

# 步骤 2: CPE 链路分流检测（读取缓存）
async def step_cpe_link_routing(ctx: FlowContext):
    # ✅ 读取缓存并恢复为 Dataclass
    dns_cache_dict = ctx.get("dns_resolution_cache")
    if dns_cache_dict:
        for domain, entry_dict in dns_cache_dict.items():
            entry = DnsResolutionEntry.from_dict(entry_dict)
            
            # ✅ 享受类型安全和自动补全
            if entry.validate():
                logger.info(
                    f"{domain}: {entry.get_all_ips()}, "
                    f"split={entry.is_split}, "
                    f"time={entry.query_time_ms:.0f}ms"
                )
    
    # 继续执行 Traceroute...
```

---

## 📝 总结

### 核心原则

1. **内部处理用 Dataclass**：享受类型安全、IDE 支持、方法扩展
2. **Context 存储用字典**：保持兼容性、简化序列化
3. **边界处转换**：写入时 `to_dict()`，读取时 `from_dict()`

### 优势总结

- ✅ **类型安全**：编码阶段发现错误，而非运行时
- ✅ **开发效率**：IDE 自动补全提升编码速度
- ✅ **可维护性**：自文档化，易于理解和重构
- ✅ **性能优化**：`slots=True` 减少内存占用
- ✅ **向后兼容**：字典格式保证与其他模块的兼容性

### 下一步行动

1. ✅ 已在 [`dns_split.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py) 中实现三个缓存数据类
2. ✅ 已更新 `test_optimized()` 和 `test_cpe_link_routing_optimized()` 使用新数据类
3. 🔄 建议在其他服务模块中也采用相同的模式（如 [connectivity.py](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\connectivity.py)）

---

如需进一步优化或有疑问，请随时提出！
