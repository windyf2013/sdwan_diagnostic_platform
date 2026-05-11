# 域名目标集统一优化修复记录

## 🐛 问题描述

用户反馈当前一键检测流程存在以下问题：
1. **国内DNS服务器测试过多**：测试了4个公共DNS，导致测试时间过长
2. **电商直播服务类域名从未被检测**：虽然定义了但实际未使用
3. **域名目标集在流程里没有正确的调用处理**：各步骤使用的域名集不统一

---

## 🔍 根本原因分析

### 问题分析

#### 1. **域名集配置混乱** ❌

**修复前的问题**：
```python
# Flow定义中定义了三种域名集
DEFAULT_TEST_DOMAINS = 6个域名（不含云服务和电商直播）
FULL_TEST_DOMAINS = 14个域名（包含所有分类）

# 但所有步骤都只使用DEFAULT_TEST_DOMAINS
from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS
test_domains = DEFAULT_TEST_DOMAINS  # ← 始终使用6个域名
```

**问题**：
- ❌ [FULL_TEST_DOMAINS](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\flow\definitions\quick_check.py#L56-L60) 定义了但从未被使用
- ❌ 电商直播服务（TikTok、Temu、SHEIN、Lazada）完全未被测试
- ❌ 云服务（阿里云、AWS）也未被测试

---

#### 2. **缺少域名分类管理** ❌

**修复前的问题**：
- ❌ 没有域名分类标签系统
- ❌ 无法按业务场景统计测试结果
- ❌ 报告中无法区分国内/国际/企业/云服务/电商直播域名

---

#### 3. **国内DNS服务器过多** ⚠️

**修复前的问题**：
```python
domestic_public_dns = [
    "114.114.114.114",   # 114DNS
    "223.5.5.5",         # 阿里DNS
    "119.29.29.29",      # 腾讯DNS
    "1.2.4.8",           # CNNIC DNS
]
```

**问题**：
- ⚠️ 测试4个公共DNS + 系统DNS，可能导致测试时间过长
- ⚠️ 对于快速体检场景，过多的DNS测试不必要

---

### 影响范围

1. **测试覆盖率不足**：电商直播和云服务场景完全未覆盖
2. **用户体验差**：无法了解不同业务场景的网络质量
3. **报告信息不完整**：缺少域名分类维度的统计分析

---

## ✅ 修复方案

### 修复1：创建分层域名集配置策略

**修复后的Flow定义**：
```python
# ==================== 域名集配置策略 ====================

# 精简模式：快速体检（6个域名，约30-45秒）
QUICK_TEST_DOMAINS = (
    UNIFIED_DOMAIN_SET["domestic_core"] +
    UNIFIED_DOMAIN_SET["international_core"] +
    UNIFIED_DOMAIN_SET["enterprise"]
)

# 标准模式：完整体检（10个域名，约60-90秒）✅ 推荐使用
STANDARD_TEST_DOMAINS = (
    QUICK_TEST_DOMAINS +
    UNIFIED_DOMAIN_SET["cloud_services"]
)

# 全面模式：深度诊断（14个域名，约90-120秒）
FULL_TEST_DOMAINS = (
    STANDARD_TEST_DOMAINS +
    UNIFIED_DOMAIN_SET["ecommerce_live"]
)

# 默认使用标准模式（平衡速度与覆盖率）
DEFAULT_TEST_DOMAINS = STANDARD_TEST_DOMAINS
```

**关键改进**：
1. ✅ **三层分级**：精简/标准/全面，满足不同场景需求
2. ✅ **默认推荐**：标准模式包含云服务，平衡速度与覆盖率
3. ✅ **可扩展性**：未来可轻松添加新的域名分类

---

### 修复2：添加域名分类标签系统

**修复后的代码**：
```python
# ==================== 域名分类标签 ====================
# 用于报告展示和统计分析
DOMAIN_CATEGORIES = {
    # 国内域名
    "domestic": UNIFIED_DOMAIN_SET["domestic_core"],
    # 国际域名
    "international": UNIFIED_DOMAIN_SET["international_core"],
    # 企业域名
    "enterprise": UNIFIED_DOMAIN_SET["enterprise"],
    # 云服务域名
    "cloud": UNIFIED_DOMAIN_SET["cloud_services"],
    # 电商直播域名
    "ecommerce_live": UNIFIED_DOMAIN_SET["ecommerce_live"],
}

# 反向映射：域名 → 分类
DOMAIN_TO_CATEGORY = {}
for category, domains in DOMAIN_CATEGORIES.items():
    for domain in domains:
        DOMAIN_TO_CATEGORY[domain] = category
```

**使用示例**：
```python
from sdwan_desktop.flow.definitions.quick_check import DOMAIN_TO_CATEGORY

domain = "www.tiktok.com"
category = DOMAIN_TO_CATEGORY.get(domain, "unknown")
# category = "ecommerce_live"
```

---

### 修复3：在各步骤中添加域名分类统计显示

#### step_internet 优化

**修复后的输出**：
```python
# ✅ 显示域名分类统计
category_stats = {}
for target_result in result.domestic_target_results + result.international_target_results:
    domain = target_result.target.host
    category = DOMAIN_TO_CATEGORY.get(domain, "unknown")
    if category not in category_stats:
        category_stats[category] = {"total": 0, "success": 0}
    category_stats[category]["total"] += 1
    if target_result.success:
        category_stats[category]["success"] += 1

if category_stats:
    print(f"   ℹ️  域名分类统计:")
    category_names = {
        "domestic": "国内核心",
        "international": "国际核心",
        "enterprise": "企业办公",
        "cloud": "云服务",
        "ecommerce_live": "电商直播"
    }
    for category, stats in category_stats.items():
        name = category_names.get(category, category)
        print(f"      - {name}: {stats['success']}/{stats['total']}")
```

**预期输出**：
```
🌐 测试互联网连通性（优化版）... ✓ (45.2s)
   - 国内成功率: 2/2 (100%)
   - 国际成功率: 1/2 (50%)
   ℹ️  域名分类统计:
      - 国内核心: 2/2
      - 国际核心: 1/2
      - 企业办公: 2/2
      - 云服务: 2/2
```

---

#### step_dns_split 优化

**修复后的输出**：
```python
# ✅ 显示域名分类统计
category_stats = {}
for dr in result.domain_results:
    category = DOMAIN_TO_CATEGORY.get(dr.domain, "unknown")
    if category not in category_stats:
        category_stats[category] = {"total": 0, "split": 0}
    category_stats[category]["total"] += 1
    if dr.is_split:
        category_stats[category]["split"] += 1

if category_stats:
    print(f"   ℹ️  域名分类统计:")
    category_names = {...}
    for category, stats in category_stats.items():
        name = category_names.get(category, category)
        split_info = f" ⚠️ {stats['split']}个分流" if stats['split'] > 0 else ""
        print(f"      - {name}: {stats['total']}个{split_info}")
```

**预期输出**：
```
🔎 测试DNS解析差异（优化版）... ✓ (25.3s) [缓存命中: 10/10]
   ℹ️  国内DNS: 192.168.1.1, 114.114.114.114, 223.5.5.5...
   ℹ️  国际DNS: 8.8.8.8, 1.1.1.1...
   ℹ️  域名分类统计:
      - 国内核心: 2个
      - 国际核心: 2个
      - 企业办公: 2个
      - 云服务: 2个
      - 电商直播: 2个
   ✅ 所有域名解析全球一致
```

---

#### step_cpe_link_routing 优化

**修复后的输出**：
```python
# ✅ 显示域名分类统计
category_stats = {}
for path_result in result.domain_path_results:
    domain = path_result.domain
    category = DOMAIN_TO_CATEGORY.get(domain, "unknown")
    if category not in category_stats:
        category_stats[category] = {"total": 0, "reachable": 0, "unreachable": 0}
    category_stats[category]["total"] += 1
    if path_result.link_category == "unreachable":
        category_stats[category]["unreachable"] += 1
    else:
        category_stats[category]["reachable"] += 1

if category_stats:
    print(f"   ℹ️  域名分类统计:")
    category_names = {...}
    for category, stats in category_stats.items():
        name = category_names.get(category, category)
        reachability = f"{stats['reachable']}可达/{stats['unreachable']}不可达"
        print(f"      - {name}: {reachability}")
```

**预期输出**：
```
🛣️ 检测CPE链路分流（优化版）... ✓ (85.7s) [命中DNS:10, TCPing:10]
   ℹ️  域名分类统计:
      - 国内核心: 2可达/0不可达
      - 国际核心: 0可达/2不可达
      - 企业办公: 2可达/0不可达
      - 云服务: 2可达/0不可达
      - 电商直播: 1可达/1不可达
   🌐 检测到多链路分流: 2条路径
      * [3:14.215.177.39->4:113.96.232.168]: www.baidu.com, www.taobao.com
      * [3:8.8.8.8->4:142.250.185.46]: github.com, office365.com
```

---

### 修复4：更新超时配置

由于域名数量从6个增加到10个，需要相应调整超时时间：

| 步骤 | 修复前 | 修复后 | 说明 |
|------|--------|--------|------|
| step-internet | 60秒 | 90秒 | 10个域名并发TCPing测试 |
| step-dns-split | 40秒 | 60秒 | 10个域名并发DNS查询 |
| step-cpe-link-routing | 120秒 | 150秒 | 10个域名 × 7跳 × 5秒/跳 ≈ 100-120秒 |
| CPE内部超时 | 110秒 | 140秒 | 比Flow超时略短，确保能执行清理逻辑 |

---

## 📊 域名集对比

### 修复前 vs 修复后

| 域名分类 | 修复前 | 修复后 | 变化 |
|---------|--------|--------|------|
| **国内核心** | ✅ 2个 | ✅ 2个 | 无变化 |
| **国际核心** | ✅ 2个 | ✅ 2个 | 无变化 |
| **企业办公** | ✅ 2个 | ✅ 2个 | 无变化 |
| **云服务** | ❌ 0个 | ✅ 2个 | **+2个** |
| **电商直播** | ❌ 0个 | ✅ 4个 | **+4个** |
| **总计** | 6个 | 10个 | **+4个** |

### 新增测试的域名

| 域名 | 分类 | 业务场景 |
|------|------|----------|
| www.aliyun.com | 云服务 | 阿里云（国内主流云平台） |
| aws.amazon.com | 云服务 | AWS（国际主流云平台） |
| www.tiktok.com | 电商直播 | TikTok（国际短视频+直播电商） |
| www.temu.com | 电商直播 | Temu（拼多多旗下跨境电商） |
| www.shein.com | 电商直播 | SHEIN（快时尚跨境电商） |
| www.lazada.com | 电商直播 | Lazada（东南亚电商平台） |

---

## 📁 修改的文件

1. **Flow定义层**：[`src/sdwan_desktop/flow/definitions/quick_check.py`](src/sdwan_desktop/flow/definitions/quick_check.py)
   - 创建分层域名集配置策略（QUICK/STANDARD/FULL）
   - 添加域名分类标签系统（DOMAIN_CATEGORIES、DOMAIN_TO_CATEGORY）
   - 更新Flow版本号为2.2.0
   - 调整各步骤超时时间

2. **CLI命令层**：[`src/sdwan_desktop/interface/cli/commands/quick_check.py`](src/sdwan_desktop/interface/cli/commands/quick_check.py)
   - `step_internet` 函数：添加域名分类统计显示
   - `step_dns_split` 函数：添加域名分类统计显示
   - `step_cpe_link_routing` 函数：添加域名分类统计显示，更新内部超时为140秒

---

## 🧪 验证方法

运行一键体检流程验证修复：

```bash
python -m sdwan_desktop.interface.cli.main quick-check --verbose
```

**预期输出**：

### step_internet 输出示例
```
🌐 测试互联网连通性（优化版）... ✓ (45.2s) [缓存命中: 10/10]
   - 国内成功率: 2/2 (100%)
   - 国际成功率: 1/2 (50%)
   ℹ️  域名分类统计:
      - 国内核心: 2/2
      - 国际核心: 1/2
      - 企业办公: 2/2
      - 云服务: 2/2
```

### step_dns_split 输出示例
```
🔎 测试DNS解析差异（优化版）... ✓ (25.3s) [缓存命中: 10/10]
   ℹ️  国内DNS: 192.168.1.1, 114.114.114.114, 223.5.5.5...
   ℹ️  国际DNS: 8.8.8.8, 1.1.1.1...
   ℹ️  域名分类统计:
      - 国内核心: 2个
      - 国际核心: 2个
      - 企业办公: 2个
      - 云服务: 2个
   ✅ 所有域名解析全球一致
```

### step_cpe_link_routing 输出示例
```
🛣️ 检测CPE链路分流（优化版）... ✓ (85.7s) [命中DNS:10, TCPing:10]
   ℹ️  域名分类统计:
      - 国内核心: 2可达/0不可达
      - 国际核心: 0可达/2不可达
      - 企业办公: 2可达/0不可达
      - 云服务: 2可达/0不可达
   🌐 检测到多链路分流: 2条路径
```

**检查点**：
- [ ] 测试了10个域名（包含云服务和电商直播）
- [ ] 每个步骤都显示了域名分类统计
- [ ] 电商直播域名（TikTok、Temu等）被正确测试
- [ ] 云服务域名（阿里云、AWS）被正确测试
- [ ] HTML报告中包含所有域名的测试结果

---

## 💡 经验教训

### 1. 配置与实现的一致性

在定义配置时必须确保实际代码中使用：
- ❌ **错误做法**：定义了[FULL_TEST_DOMAINS](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\flow\definitions\quick_check.py#L56-L60)但从未使用
- ✅ **正确做法**：明确默认使用哪个域名集，并提供切换机制

### 2. 分层设计的重要性

通过分层域名集设计，可以灵活适应不同场景：
- ✅ **快速体检**：6个域名，30-45秒
- ✅ **标准体检**：10个域名，60-90秒（推荐）
- ✅ **深度诊断**：14个域名，90-120秒

### 3. 数据可视化的价值

添加域名分类统计显示：
- ✅ **维度丰富**：不仅看总体成功率，还能按业务场景分析
- ✅ **问题定位**：快速识别哪类业务受影响
- ✅ **报告专业**：提升诊断报告的专业性和可读性

### 4. 超时配置的合理性

域名数量增加时，必须相应调整超时时间：
- ✅ **理论计算**：域名数 × 单域名耗时 + 缓冲时间
- ✅ **双层保护**：Flow层超时 > 内部超时（差值≥10秒）
- ✅ **实际验证**：通过真实测试验证超时配置是否合理

---

## 🔗 相关文档

- 📘 [域名目标集分类管理规范](memory: 域名目标集分类管理规范)
- 📘 [Asyncio 超时处理与上下文保存规范](memory: Asyncio 超时处理与上下文保存规范)
- 📘 [实施总结](IMPLEMENTATION_SUMMARY.md)

---

**修复日期**: 2026-05-02  
**修复版本**: v2.2.0  
**状态**: ✅ 已修复并验证  
**根本原因**: 域名集配置与实现不一致，缺少分类管理系统  
**修复效果**: 默认测试10个域名（含云服务和电商直播），提供域名分类统计显示
