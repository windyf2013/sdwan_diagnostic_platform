# DNS分流测试域名精简配置说明

**日期**: 2026-05-03  
**版本**: v1.0.0  
**状态**: 用户测试阶段临时配置

---

## 📋 变更概述

### 修改内容
将GUI和CLI的DNS分流测试（step-dns-split）统一配置为仅测试2个核心域名，而非标准的10个域名集。

### 影响范围
- ✅ `src/sdwan_desktop/interface/cli/commands/quick_check.py` - CLI实现
- ✅ `src/sdwan_desktop/interface/gui/tabs/quick_check_tab.py` - GUI实现

---

## ⚠️ 重要说明

### 这是用户测试阶段的特殊配置

```python
# ⚠️ 用户测试阶段特殊配置：仅测试2个核心域名
# 说明：为加快测试速度，临时将域名集从10个精简为2个（baidu + google）
# 注意：这会降低DNS劫持检测的覆盖率，生产环境应恢复使用DEFAULT_TEST_DOMAINS
test_domains = ["www.baidu.com", "www.google.com"]
```

### 配置原因
1. **加快测试速度**：减少DNS查询次数，缩短整体测试时间
2. **快速验证流程**：在开发和调试阶段快速验证端到端流程
3. **降低资源消耗**：减少网络探测对系统资源的占用

### 风险提示
❌ **DNS劫持检测覆盖率从100%降至20%**（2/10个域名）

**缺失的测试场景**：
- ❌ 国内电商：www.taobao.com
- ❌ 国际视频：www.youtube.com
- ❌ 企业办公：github.com, office365.com
- ❌ 云服务：www.aliyun.com, aws.amazon.com

**可能的后果**：
- 无法检测taobao.com等域名的DNS劫持问题
- 无法发现youtube.com等域名的DNS污染问题
- GUI和CLI的诊断结果与标准模式不一致

---

## 🔧 技术细节

### 修改前（标准模式）
```python
# CLI和GUI都使用统一域名集
from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS

result = await dns_split_tester.test_optimized(
    domains=DEFAULT_TEST_DOMAINS,  # 10个域名
    domestic_dns=all_domestic_dns,
    international_dns=international_dns,
    ctx=ctx,
    use_cache=True
)
```

### 修改后（测试模式）
```python
# ⚠️ 用户测试阶段特殊配置
test_domains = ["www.baidu.com", "www.google.com"]

result = await dns_split_tester.test_optimized(
    domains=test_domains,  # 仅2个域名
    domestic_dns=all_domestic_dns,
    international_dns=international_dns,
    ctx=ctx,
    use_cache=True
)
```

---

## 📊 性能对比

| 指标 | 标准模式（10域名） | 测试模式（2域名） | 改善幅度 |
|------|------------------|------------------|---------|
| **DNS查询次数** | 40次（10×4） | 8次（2×4） | ⬇️ 80% |
| **预计耗时** | 40-60秒 | 10-15秒 | ⬇️ 75% |
| **缓存命中率** | 取决于上下文 | 更高（域名少） | ⬆️ 提升 |
| **覆盖率** | 100%（5类业务） | 20%（仅搜索） | ⬇️ 80% |

---

## 🎯 恢复标准模式的步骤

当需要恢复完整的DNS分流测试时，执行以下操作：

### 步骤1: 修改CLI代码
**文件**: `src/sdwan_desktop/interface/cli/commands/quick_check.py`

```python
# 删除或注释掉测试配置
# test_domains = ["www.baidu.com", "www.google.com"]

# 恢复使用统一域名集
from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS

result = await dns_split_tester.test_optimized(
    domains=DEFAULT_TEST_DOMAINS,  # ✅ 恢复：10个域名
    domestic_dns=all_domestic_dns,
    international_dns=international_dns,
    ctx=ctx,
    use_cache=True
)
```

### 步骤2: 修改GUI代码
**文件**: `src/sdwan_desktop/interface/gui/tabs/quick_check_tab.py`

```python
# 删除或注释掉测试配置
# test_domains = ["www.baidu.com", "www.google.com"]

# 恢复使用统一域名集
from sdwan_desktop.flow.definitions.quick_check import DEFAULT_TEST_DOMAINS

result = await dns_split_tester.test_optimized(
    domains=DEFAULT_TEST_DOMAINS,  # ✅ 恢复：10个域名
    domestic_dns=system_dns_servers,
    international_dns=["8.8.8.8", "1.1.1.1"],
    ctx=ctx,
    use_cache=True
)
```

### 步骤3: 验证修改
运行一键体检，检查日志输出：
```bash
# CLI
agentctl quick-check --verbose

# 预期输出：
# 🔎 测试DNS解析差异（优化版）... ✓ (45.2s) [缓存命中: 0/10]
#    ℹ️  域名分类统计:
#       - 国内核心: 2个
#       - 国际核心: 2个
#       - 企业办公: 2个
#       - 云服务: 2个
#       - 电商直播: 2个
```

---

## 📝 相关规范参考

### 违反的规范
⚠️ 本次修改**暂时违反**了以下规范（作为测试阶段的权衡）：

1. **域名目标集分类管理规范**
   - 要求：域名应按业务场景分类管理
   - 现状：仅测试搜索引擎类别

2. **多接口实现一致性规范**
   - 要求：GUI和CLI应与标准配置保持一致
   - 现状：两者一致但偏离标准配置

3. **域名集统一性验证规范**
   - 要求：禁止硬编码域名列表
   - 现状：临时硬编码用于测试

### 遵守的规范
✅ 本次修改**仍然遵守**以下规范：

1. **跨步骤数据复用优化规范**
   - DNS解析结果仍会存入Context缓存
   - CPE链路分流测试可复用缓存数据

2. **DNS服务器测试配置规范**
   - 国内DNS保持2个（114 + 223）
   - 国际DNS保持2个（8.8.8.8 + 1.1.1.1）

---

## 🔍 验证方法

### 方法1: 检查日志输出
```bash
# 运行一键体检
agentctl quick-check

# 观察DNS分流测试的输出
# 测试模式应显示：✓ (12.3s) [缓存命中: 0/2]
# 标准模式应显示：✓ (45.2s) [缓存命中: 0/10]
```

### 方法2: 检查HTML报告
打开生成的HTML报告，查看"DNS解析一致性"章节：
- **测试模式**：仅显示2个域名的解析结果
- **标准模式**：显示10个域名的解析结果，包含5个业务分类统计

### 方法3: 代码审查
```bash
# 搜索测试配置标记
grep -r "用户测试阶段特殊配置" src/

# 应该找到2处：
# - src/sdwan_desktop/interface/cli/commands/quick_check.py
# - src/sdwan_desktop/interface/gui/tabs/quick_check_tab.py
```

---

## 💡 最佳实践建议

### 开发阶段
✅ **推荐使用测试模式**：
- 快速验证端到端流程
- 减少等待时间
- 降低调试成本

### 测试阶段
⚠️ **建议使用标准模式**：
- 全面验证DNS劫持检测能力
- 确保所有业务场景覆盖
- 生成完整的诊断报告

### 生产环境
✅ **必须使用标准模式**：
- 保证诊断结果的准确性
- 符合安全审计要求
- 提供完整的风险分析

---

## 📌 总结

本次修改是**用户测试阶段的临时配置**，目的是加快测试速度。虽然降低了DNS劫持检测的覆盖率，但在开发和调试阶段是可接受的权衡。

**关键要点**：
1. ✅ GUI和CLI保持一致（都使用2个域名）
2. ⚠️ 明确标注为"用户测试阶段特殊配置"
3. ⚠️ 提醒生产环境应恢复标准配置
4. ✅ 保留完整的恢复步骤文档

**下一步行动**：
- 在测试完成后，及时恢复为标准模式
- 更新项目文档，记录此临时配置的适用范围
- 考虑添加配置开关，支持动态切换测试/标准模式
