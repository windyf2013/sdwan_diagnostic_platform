# HTML 报告 DNS 分流和路径追踪显示问题修复记录

## 🐛 问题描述

### 用户反馈
1. **HTML 报告中，网络探测部分不显示 DNS 分流检测的信息**
2. **路径追踪中，可达的域名需要显示所有节点，包括超时跳点**

---

## 🔍 根本原因分析

### 问题 1：DNS 分流结果未存入 Context

**位置**：[`dns_split.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py)

**问题分析**：
- Flow 定义中使用 `handler="dns_split.test_optimized"`，直接调用服务层方法
- [test_optimized](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py#L625-L703) 方法只将 DNS 解析缓存（`dns_resolution_cache`）存入 Context
- **没有将整个 `DnsSplitTestResult` 对象存入 Context**
- 导致 CLI/GUI 中的代码无法从 Context 获取 [dns_split_result](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\verify_dns_split_in_evidence.py#L29-L29)，无法保存到证据链
- 最终报告生成器无法从证据链中提取数据

**同样的问题也存在于 CPE 链路分流结果**：
- [test_cpe_link_routing_optimized](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py#L1452-L1537) 方法只将 Traceroute 缓存存入 Context
- **没有将整个 [CpeLinkRouteResult](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py#L404-L432) 对象存入 Context**

### 问题 2：路径追踪缺少 hostnames 字段

**位置**：[`html_builder.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\reporter\html_builder.py)

**问题分析**：
- 在转换 Traceroute 跳点信息时，只提取了 `hop_number`、`ip_addresses`、[rtts](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\core\types\probe.py#L90-L90)、`is_timeout`
- **缺少 `hostnames` 字段**
- 导致 HTML 模板中无法显示跳点的域名信息（如果有的话）

---

## ✅ 修复方案

### 修复 1：将完整结果存入 Context

#### 1.1 DNS 分流测试结果

**文件**：[`dns_split.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py) 第 690-703 行

```python
# ✅ 将 DNS 解析结果转换为结构化缓存并存入 Context
dns_cache_entries: Dict[str, DnsResolutionEntry] = {}
for domain_result in result.domain_results:
    entry = DnsResolutionEntry(
        domain=domain_result.domain,
        domestic_ips=[r.resolved_ip for r in domain_result.domestic_results if r.success],
        international_ips=[r.resolved_ip for r in domain_result.international_results if r.success],
        is_split=domain_result.is_split,
        query_time_ms=domain_result.total_duration_ms
    )
    dns_cache_entries[domain_result.domain] = entry

# 存入 Context 时转换为字典（保持兼容性）
ctx.set("dns_resolution_cache", {
    k: v.to_dict() for k, v in dns_cache_entries.items()
})

# ✅ 关键修复：将整个测试结果也存入 Context，供报告生成器使用
ctx.set("dns_split_result", result)

logger.info(
    f"DNS解析结果已缓存到Context（{len(dns_cache_entries)}个域名），可供后续步骤复用",
    extra={"trace_id": ctx.trace_id}
)

return result
```

#### 1.2 CPE 链路分流测试结果

**文件**：[`dns_split.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py) 第 1520-1537 行

```python
# 存入 Context 时转换为字典（保持兼容性）
ctx.set("traceroute_results_cache", {
    k: v.to_dict() for k, v in traceroute_entries.items()
})

# ✅ 关键修复：将整个测试结果也存入 Context，供报告生成器使用
ctx.set("cpe_link_routing_result", result)

logger.info(
    f"Traceroute结果已缓存到Context（{len(traceroute_entries)}个域名），可供报告生成使用",
    extra={"trace_id": ctx.trace_id}
)

return result
```

### 修复 2：添加 hostnames 字段

**文件**：[`html_builder.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\reporter\html_builder.py) 第 358-385 行

```python
else:
    # 转换 TracerouteHopInfo 列表
    full_path = []
    for hop in getattr(dr, 'full_path', []):
        if isinstance(hop, dict):
            full_path.append(hop)
        else:
            full_path.append({
                "hop_number": getattr(hop, 'hop_number', 0),
                "ip_addresses": getattr(hop, 'ip_addresses', []),
                "hostnames": getattr(hop, 'hostnames', []),  # ✅ 添加 hostnames 字段
                "rtts": getattr(hop, 'rtts', []),
                "is_timeout": getattr(hop, 'is_timeout', False),
            })
    
    post_cpe_hops = []
    for hop in getattr(dr, 'post_cpe_hops', []):
        if isinstance(hop, dict):
            post_cpe_hops.append(hop)
        else:
            post_cpe_hops.append({
                "hop_number": getattr(hop, 'hop_number', 0),
                "ip_addresses": getattr(hop, 'ip_addresses', []),
                "hostnames": getattr(hop, 'hostnames', []),  # ✅ 添加 hostnames 字段
                "rtts": getattr(hop, 'rtts', []),
                "is_timeout": getattr(hop, 'is_timeout', False),
            })
```

---

## 📋 验证步骤

### 1. 重新运行一键体检

```powershell
cd d:\ai-missions\deepseek\sdwan_diagnostic_platform

# CLI 模式
python -m sdwan_desktop.interface.cli.main quick-check --output test_fix_complete.html

# GUI 模式
python -m sdwan_desktop.interface.gui.main
```

### 2. 检查 HTML 报告

打开生成的 HTML 报告，验证以下两点：

#### ✅ 验证点 1：DNS 分流检测信息显示

找到 **"🌐 网络探测"** → **"🔍 DNS解析一致性测试"** 章节，应该看到：

| 测试域名 | DNS区域 | 解析结果 | 一致性 |
|---------|---------|---------|-------|
| www.baidu.com | 🇨🇳 国内DNS<br/>114.114.114.114, 223.5.5.5 | 39.156.70.46, 39.156.70.239 | 存在地域差异 |
| | 🌍 国际DNS<br/>8.8.8.8, 1.1.1.1 | 39.156.70.46 | |

**关键验证**：
- ✅ DNS解析一致性测试章节正常显示
- ✅ 每个域名都有国内/国际 DNS 解析结果
- ✅ IP 地址以逗号分隔的字符串形式显示

#### ✅ 验证点 2：路径追踪显示所有节点（包括超时跳点）

找到 **"🛣️ CPE链路分流检测"** → **"详细路径分析"** 章节，应该看到：

**对于可达的域名**：
```
🌐 www.baidu.com (39.156.70.46)
路径类别: 国内链路 | 置信度: 0.85

跳数 | IP地址 | 延迟
-----|--------|------
1    | 192.168.1.1 | 2.3 ms
2    | 10.0.0.1 | 5.1 ms
3    | * (请求超时) | -
4    | 202.97.33.1 | 15.2 ms
5    | * (请求超时) | -
6    | 39.156.70.46 | 25.8 ms
```

**关键验证**：
- ✅ **所有跳点都显示**，包括超时跳点（第 3、5 跳）
- ✅ 超时跳点显示为 `* (请求超时)` 和 `-`
- ✅ 超时跳点背景色为黄色（`#fff3cd`）
- ✅ 正常跳点显示 IP 地址和延迟
- ✅ 如果有 hostname，会显示在 IP 下方

---

## 💡 经验总结

### 教训
1. **Flow 服务层方法必须将完整结果存入 Context**：否则上层代码无法获取数据进行报告生成
2. **数据转换时要保留所有必要字段**：如 `hostnames` 字段对路径分析很重要
3. **分层架构中的数据传递要清晰**：
   - Service 层 → Context（完整结果 + 缓存）
   - CLI/GUI 层 → Evidence.config_snapshots（从 Context 读取并保存）
   - Reporter 层 → HTML 模板（从 Evidence 提取并渲染）

### 最佳实践
1. **Context 数据存储规范**：
   ```python
   # ✅ 正确做法：同时存储缓存和完整结果
   ctx.set("dns_resolution_cache", {...})  # 用于步骤间复用
   ctx.set("dns_split_result", result)      # 用于报告生成
   
   # ❌ 错误做法：只存储缓存
   ctx.set("dns_resolution_cache", {...})
   ```

2. **数据转换完整性检查**：
   - 对照目标数据结构（如 HTML 模板需要的字段）
   - 确保所有字段都被正确提取和转换
   - 添加单元测试验证转换逻辑

3. **调试技巧**：
   - 在关键位置添加日志，记录数据流转情况
   - 打印 Context 中的所有键，确认数据是否正确存入
   - 检查 Evidence.config_snapshots 的内容

---

## 📝 相关文件

| 文件 | 修改内容 | 状态 |
|------|---------|------|
| [`dns_split.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py) | 在 `test_optimized()` 中添加 `ctx.set("dns_split_result", result)` | ✅ 已修复 |
| [`dns_split.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py) | 在 `test_cpe_link_routing_optimized()` 中添加 `ctx.set("cpe_link_routing_result", result)` | ✅ 已修复 |
| [`html_builder.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\reporter\html_builder.py) | 在跳点转换中添加 `hostnames` 字段 | ✅ 已修复 |

---

**修复完成时间**：2026-05-02  
**影响范围**：HTML 报告中的 DNS 分流检测和路径追踪显示  
**风险等级**：低（仅调整数据传递逻辑，不影响核心功能）
