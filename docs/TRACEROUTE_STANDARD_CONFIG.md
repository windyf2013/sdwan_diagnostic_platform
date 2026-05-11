# Traceroute 标准配置速查表

## 📏 核心规则

```yaml
# Traceroute 标准配置（CPE链路分流检测）
max_hops: 7              # 每域名跟踪7个跃点
probes_per_hop: 3        # 每个跃点测试3次
timeout_per_probe: 5     # 单次超时时间5秒
total_timeout: 105       # 总超时 = 7 × 3 × 5 = 105秒
```

## 🔢 计算公式

```
总超时时间 = max_hops × probes_per_hop × timeout_per_probe
           = 7 × 3 × 5
           = 105秒
```

## ⚙️ Flow层配置

```python
# Flow定义
StepDefinition(
    id="step-cpe-link-routing",
    name="CPE链路分流检测",
    handler="dns_split.test_cpe_link_routing_optimized",
    timeout_seconds=120  # Flow层超时 = 105秒 + 15秒缓冲
)

# 内部保护超时
result = await asyncio.wait_for(
    dns_split_tester.test_cpe_link_routing_optimized(...),
    timeout=110  # 略短于Flow超时，确保能执行except块
)
```

## 📊 超时层级

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
```

## 🎯 适用场景

- ✅ **CPE链路分流检测**（主要用途）
- ✅ **企业内网路径追踪**
- ✅ **分支到总部连通性验证**

## ⚠️ 注意事项

1. **7跳已足够**：前7跳通常能识别CPE出口后的路径差异
2. **实际耗时更短**：通常只需30-50秒（大部分跳点响应较快）
3. **并发优化**：多个域名并发执行时，总耗时≈单个域名的耗时
4. **特殊场景可调整**：跨国业务等复杂场景可增加跳数至15-22跳

## 📚 详细文档

完整配置说明和场景分析请参考：
- [TRACEROUTE_HOP_CONFIGURATION_GUIDE.md](TRACEROUTE_HOP_CONFIGURATION_GUIDE.md)

---

**版本**: v1.0  
**更新日期**: 2026-05-02  
**状态**: ✅ 生产环境标准配置
