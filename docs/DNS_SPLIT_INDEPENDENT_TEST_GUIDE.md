# DNS 分流独立测试模块使用指南

## 📋 概述

`dns-split-test` 是一个独立的 CLI 命令，允许您单独运行 DNS 分流测试模块，无需执行完整的一键体检流程。这对于快速验证 DNS 配置、调试网络问题或进行专项测试非常有用。

---

## 🚀 快速开始

### 基本用法

```powershell
# 使用默认配置（8个统一域名集）
python -m sdwan_desktop.interface.cli.main dns-split-test

# 查看详细帮助信息
python -m sdwan_desktop.interface.cli.main dns-split-test --help
```

### 预期输出

```text
🔍 DNS 分流独立测试模块
============================================================

📋 测试配置:
   - 测试域名: 8 个
     1. www.baidu.com
     2. www.taobao.com
     3. www.google.com
     4. www.youtube.com
     5. github.com
     6. office365.com
     7. www.aliyun.com
     8. aws.amazon.com

   - 国内DNS: 114.114.114.114, 223.5.5.5
   - 国际DNS: 8.8.8.8, 1.1.1.1

🚀 开始执行 DNS 分流测试...
------------------------------------------------------------

============================================================
✅ 测试完成 (耗时: 3.5s)
============================================================

📊 测试结果摘要:
   - 总测试域名数: 8
   - 全球一致: 6 个
   - 存在地域差异: 2 个

⚠️  发现分流异常的域名:
   - www.baidu.com
     国内DNS: [{'resolved_ip': '39.156.70.46'}]
     国际DNS: [{'resolved_ip': '39.156.70.46'}, {'resolved_ip': '39.156.70.239'}]
     说明: 国内外DNS解析结果不一致，可能存在CDN调度策略
```

---

## 🔧 高级用法

### 1. 指定自定义域名列表

```powershell
# 测试单个域名
python -m sdwan_desktop.interface.cli.main dns-split-test -d "www.tiktok.com"

# 测试多个域名（逗号分隔）
python -m sdwan_desktop.interface.cli.main dns-split-test -d "www.baidu.com,www.google.com,www.temu.com"

# 测试电商直播场景域名
python -m sdwan_desktop.interface.cli.main dns-split-test -d "www.tiktok.com,www.temu.com,www.shein.com,www.lazada.com"
```

### 2. 指定自定义 DNS 服务器

```powershell
# 使用单个国内 DNS
python -m sdwan_desktop.interface.cli.main dns-split-test --domestic-dns "114.114.114.114"

# 使用多个国际 DNS
python -m sdwan_desktop.interface.cli.main dns-split-test --international-dns "8.8.8.8,1.1.1.1,9.9.9.9"

# 同时指定国内和国际 DNS
python -m sdwan_desktop.interface.cli.main dns-split-test \
    --domestic-dns "223.5.5.5,119.29.29.29" \
    --international-dns "8.8.8.8,1.1.1.1"
```

### 3. 启用详细输出模式

```powershell
# 显示每个域名的详细解析结果
python -m sdwan_desktop.interface.cli.main dns-split-test --verbose

# 简写形式
python -m sdwan_desktop.interface.cli.main dns-split-test -v
```

**详细输出示例**：
```text
📝 详细结果:

   [www.baidu.com]
     是否分流: 是
     国内解析: [{'resolved_ip': '39.156.70.46', 'rtt_avg': 15.2}]
     国际解析: [{'resolved_ip': '39.156.70.46', 'rtt_avg': 18.5}, {'resolved_ip': '39.156.70.239', 'rtt_avg': 22.1}]
     耗时: 45ms

   [www.google.com]
     是否分流: 否
     国内解析: [{'resolved_ip': '142.250.188.14', 'rtt_avg': 120.3}]
     国际解析: [{'resolved_ip': '142.250.188.14', 'rtt_avg': 118.7}]
     耗时: 38ms
```

---

## 📊 应用场景

### 场景 1：快速验证 DNS 配置

当您怀疑 DNS 配置有问题时，可以快速运行此命令进行验证：

```powershell
# 测试公司常用域名
python -m sdwan_desktop.interface.cli.main dns-split-test -d "mail.company.com,intranet.company.com"
```

### 场景 2：跨境电商网络诊断

针对电商直播平台进行专项测试：

```powershell
python -m sdwan_desktop.interface.cli.main dns-split-test \
    -d "www.tiktok.com,www.temu.com,www.shein.com" \
    --verbose
```

### 场景 3：对比不同 DNS 服务商

测试不同 DNS 服务器的解析效果：

```powershell
# 测试阿里云 DNS vs 腾讯云 DNS
python -m sdwan_desktop.interface.cli.main dns-split-test \
    --domestic-dns "223.5.5.5" \
    --international-dns "119.29.29.29"
```

### 场景 4：集成到自动化脚本

可以将此命令集成到 CI/CD 或监控脚本中：

```powershell
# 检查关键业务域名的 DNS 一致性
$result = python -m sdwan_desktop.interface.cli.main dns-split-test -d "api.company.com" --verbose

# 解析输出并触发告警
if ($result -match "存在地域差异") {
    Send-Alert "DNS 分流异常 detected!"
}
```

---

## 🔍 参数说明

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--domains` | `-d` | String | 统一域名集（8个） | 测试域名列表，逗号分隔 |
| `--domestic-dns` | - | String | `114.114.114.114,223.5.5.5` | 国内 DNS 服务器，逗号分隔 |
| `--international-dns` | - | String | `8.8.8.8,1.1.1.1` | 国际 DNS 服务器，逗号分隔 |
| `--verbose` | `-v` | Flag | False | 启用详细输出模式 |
| `--help` | -h | - | - | 显示帮助信息 |

---

## 💡 技术细节

### 1. 与一键体检的关系

- **一键体检 (`quick-check`)**：执行完整的诊断流程（系统采集 → 网关测试 → DNS 测试 → 互联网连通性 → DNS 分流 → CPE 链路分流）
- **DNS 分流独立测试 (`dns-split-test`)**：仅执行 DNS 分流测试步骤，适合快速验证和调试

### 2. 缓存机制

- **独立测试模式**：默认不使用缓存（`use_cache=False`），确保每次测试都是最新的解析结果
- **一键体检模式**：使用缓存复用（`use_cache=True`），避免重复查询提升性能

### 3. 数据来源

测试使用的域名来自 [`UNIFIED_DOMAIN_SET`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\flow\definitions\quick_check.py#L14-L46)，包含：
- 国内核心服务（2个）
- 国际核心服务（2个）
- 企业办公服务（2个）
- 云服务平台（2个）

### 4. 判定标准

**DNS 分流判定逻辑**：
- ✅ **全球一致**：国内外 DNS 解析出相同的 IP 地址
- ⚠️ **存在地域差异**：国内外 DNS 解析出不同的 IP 地址（可能是 CDN 智能调度或 DNS 污染防护）

---

## 🐛 常见问题

### Q1: 为什么有些域名显示"存在地域差异"？

**A**: 这通常是正常的 CDN 调度策略。例如：
- 百度会根据用户地理位置返回最近的 CDN 节点
- Google 在全球有多个数据中心，不同 DNS 可能返回不同 IP

**判断方法**：
- 如果两个 IP 都能正常访问 → 正常 CDN 调度
- 如果某个 IP 无法访问 → 可能存在 DNS 污染或防火墙限制

### Q2: 如何确认 DNS 是否被污染？

**A**: 结合以下指标判断：
1. 国际 DNS 解析出的 IP 在国内无法访问
2. 国内 DNS 解析出的 IP 与国际完全不同
3. 使用 `ping` 或 `tcping` 验证 IP 可达性

```powershell
# 先运行 DNS 分流测试
python -m sdwan_desktop.interface.cli.main dns-split-test -d "www.example.com" --verbose

# 再手动 ping 国际 DNS 返回的 IP
ping <国际IP地址>
```

### Q3: 测试耗时过长怎么办？

**A**: 可能的原因和优化方案：
1. **DNS 服务器响应慢** → 更换更快的 DNS 服务器（如 223.5.5.5）
2. **网络延迟高** → 选择离您地理位置更近的 DNS 服务器
3. **测试域名过多** → 减少 `-d` 参数中的域名数量

### Q4: 如何将结果导出为文件？

**A**: 目前支持控制台输出，如需保存到文件：

```powershell
# PowerShell
python -m sdwan_desktop.interface.cli.main dns-split-test --verbose > dns_split_result.txt

# Linux/Mac
python -m sdwan_desktop.interface.cli.main dns-split-test --verbose | tee dns_split_result.txt
```

---

## 📝 相关文档

- [一键体检优化文档](./QUICK_CHECK_OPTIMIZATION.md)
- [DNS 分流检测原理](./DNS_SPLIT_DETECTION_GUIDE.md)
- [统一域名集配置](../src/sdwan_desktop/flow/definitions/quick_check.py)

---

**最后更新**：2026-05-02  
**维护者**：SD-WAN 诊断平台团队
