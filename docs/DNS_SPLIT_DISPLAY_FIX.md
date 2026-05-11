# HTML 报告 DNS 分流检测显示问题修复记录

## 🐛 问题描述

### 用户反馈
HTML 报告中，网络探测部分不显示 DNS 分流检测的信息。

### 预期行为
报告应该显示：
- 🔍 **DNS解析一致性测试**独立章节
- 每个域名的国内/国际 DNS 解析结果对比
- 一致性判定（全球一致 / 存在地域差异）

---

## 🔍 根本原因分析

经过排查，发现以下问题：

### 问题 1：Flow 配置缺少共享上下文键

**位置**：[`quick_check.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\flow\definitions\quick_check.py) 第 143-153 行

**问题**：`shared_context_keys` 中只包含了缓存数据，但没有包含实际的结果对象（如 `dns_split_result` 和 `cpe_link_routing_result`）。

```python
# ❌ 修改前
"shared_context_keys": [
    "dns_resolution_cache",      # DNS解析缓存
    "tcping_results_cache",      # TCPing结果缓存
    "unified_domain_set"         # 统一域名集
]

# ✅ 修改后
"shared_context_keys": [
    "dns_resolution_cache",      # DNS解析缓存
    "tcping_results_cache",      # TCPing结果缓存
    "traceroute_results_cache",  # Traceroute结果缓存
    "unified_domain_set",        # 统一域名集
    "dns_split_result",          # ✅ DNS分流测试结果
    "cpe_link_routing_result"    # ✅ CPE链路分流检测结果
]
```

### 问题 2：DNS 结果提取逻辑不正确

**位置**：[`html_builder.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\reporter\html_builder.py) 第 283-306 行

**问题**：在提取 DNS 解析结果时，直接使用 `str()` 转换整个对象，导致输出类似 `[{'resolved_ip': '39.156.70.46'}]` 这样的 Python 对象字符串表示，而不是简洁的 IP 列表。

```python
# ❌ 修改前
connectivity["dns_split_details"].append({
    "domain": domain,
    "is_split": is_split,
    "description": description,
    "domestic_ips": str(domestic_res),           # ← 输出: [{'resolved_ip': '39.156.70.46'}]
    "international_ips": str(international_res), # ← 输出: [{'resolved_ip': '39.156.70.46'}]
})

# ✅ 修改后
def extract_ips(res_list):
    """从 DNS 解析结果列表中提取 IP 地址"""
    if isinstance(res_list, list):
        ips = []
        for res in res_list:
            if isinstance(res, dict):
                ip = res.get("resolved_ip", "")
                if ip:
                    ips.append(ip)
            else:
                ip = getattr(res, "resolved_ip", "")
                if ip:
                    ips.append(ip)
        return ", ".join(ips) if ips else "无解析记录"
    elif isinstance(res_list, str):
        return res_list
    else:
        return "无解析记录"

domestic_ips_str = extract_ips(domestic_res)
international_ips_str = extract_ips(international_res)

connectivity["dns_split_details"].append({
    "domain": domain,
    "is_split": is_split,
    "description": description,
    "domestic_ips": domestic_ips_str,           # ← 输出: 39.156.70.46, 39.156.70.239
    "international_ips": international_ips_str, # ← 输出: 39.156.70.46
})
```

---

## ✅ 修复方案

### 修复 1：更新 Flow 配置

**文件**：[`quick_check.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\flow\definitions\quick_check.py)

```python
config={
    "parallel_groups": [["step-gateway", "step-dns"]],
    "continue_on_error": True,
    "save_snapshots": True,
    "shared_context_keys": [
        "dns_resolution_cache",      # DNS解析缓存
        "tcping_results_cache",      # TCPing结果缓存
        "traceroute_results_cache",  # Traceroute结果缓存
        "unified_domain_set",        # 统一域名集
        "dns_split_result",          # ✅ DNS分流测试结果
        "cpe_link_routing_result"    # ✅ CPE链路分流检测结果
    ]
}
```

### 修复 2：优化 DNS 结果提取逻辑

**文件**：[`html_builder.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\reporter\html_builder.py)

添加了 `extract_ips()` 辅助函数，正确提取 IP 地址：

```python
def extract_ips(res_list):
    """从 DNS 解析结果列表中提取 IP 地址"""
    if isinstance(res_list, list):
        ips = []
        for res in res_list:
            if isinstance(res, dict):
                ip = res.get("resolved_ip", "")
                if ip:
                    ips.append(ip)
            else:
                ip = getattr(res, "resolved_ip", "")
                if ip:
                    ips.append(ip)
        return ", ".join(ips) if ips else "无解析记录"
    elif isinstance(res_list, str):
        return res_list
    else:
        return "无解析记录"
```

---

## 📋 验证步骤

### 1. 重新运行一键体检

```powershell
cd d:\ai-missions\deepseek\sdwan_diagnostic_platform

# CLI 模式
python -m sdwan_desktop.interface.cli.main quick-check --output test_dns_split_fix.html

# GUI 模式
python -m sdwan_desktop.interface.gui.main
```

### 2. 检查 HTML 报告

打开生成的 HTML 报告，找到 **"🌐 网络探测"** 章节，应该看到：

#### 🔍 DNS解析一致性测试

| 测试域名 | DNS区域 | 解析结果 | 一致性 |
|---------|---------|---------|-------|
| www.baidu.com | 🇨🇳 国内DNS<br/>114.114.114.114, 223.5.5.5 | 39.156.70.46, 39.156.70.239 | 存在地域差异 |
| | 🌍 国际DNS<br/>8.8.8.8, 1.1.1.1 | 39.156.70.46 | |

### 3. 关键验证点

- ✅ **DNS解析一致性测试章节显示**
- ✅ **每个域名都有国内/国际 DNS 解析结果**
- ✅ **IP 地址以逗号分隔的字符串形式显示**（而非 Python 对象）
- ✅ **一致性标签正确显示**（全球一致 / 存在地域差异）

---

## 💡 经验总结

### 教训
1. **Flow 配置必须包含所有需要传递的数据键**：否则 Context 中的数据无法保存到证据链
2. **数据提取时要考虑展示层的可读性**：不要直接 `str()` 转换复杂对象
3. **添加辅助函数提高代码可维护性**：如 `extract_ips()` 函数

### 最佳实践
1. **Flow 配置清单**：
   ```python
   "shared_context_keys": [
       # 缓存数据（用于步骤间复用）
       "dns_resolution_cache",
       "tcping_results_cache",
       
       # 最终结果（用于报告生成）
       "dns_split_result",
       "cpe_link_routing_result"
   ]
   ```

2. **数据提取原则**：
   - 从原始数据中提取展示层需要的字段
   - 避免直接将复杂对象传递给模板
   - 使用辅助函数处理数据转换逻辑

3. **调试技巧**：
   - 在报告生成器中添加日志，记录是否找到数据
   - 打印 `config_snapshots.keys()` 确认数据结构
   - 检查模板中的条件判断是否正确

---

## 📝 相关文件

| 文件 | 修改内容 | 状态 |
|------|---------|------|
| [`quick_check.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\flow\definitions\quick_check.py)（Flow定义） | 添加 `dns_split_result` 和 `cpe_link_routing_result` 到共享上下文键 | ✅ 已修复 |
| [`html_builder.py`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\reporter\html_builder.py) | 优化 DNS 结果提取逻辑，添加 `extract_ips()` 函数 | ✅ 已修复 |

---

**修复完成时间**：2026-05-02  
**影响范围**：HTML 报告中的 DNS 分流检测显示  
**风险等级**：低（仅调整数据提取逻辑，不影响核心功能）
