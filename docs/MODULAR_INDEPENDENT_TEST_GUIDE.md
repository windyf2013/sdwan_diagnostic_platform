# 一键体检模块化独立测试完全指南

## 📋 概述

为了提升开发效率和故障排查速度，我们为**一键体检流程的每个模块**都提供了独立的 CLI 测试命令。这些命令可以直接调用 Service 层的核心逻辑，无需执行完整的诊断流程。

---

## 🎯 命令总览

| 序号 | 模块 | 命令 | 功能说明 | 依赖 |
|------|------|------|---------|------|
| 1 | **系统采集** | `system-collect` | 采集操作系统、网络配置、路由表等信息 | 无 |
| 2 | **网关测试** | `gateway-test` | 测试默认网关的 ICMP 连通性 | 可选：系统采集 |
| 3 | **DNS 解析** | `dns-resolve` | 测试 DNS 服务器响应和解析结果 | 可选：系统采集 |
| 4 | **互联网连通** | `internet-test` | 测试国内外目标的 TCP 连通性 | 可选：DNS 缓存 |
| 5 | **DNS 分流** | `dns-split-test` | 对比国内外 DNS 解析差异 | 可选：DNS 缓存 |
| 6 | **CPE 链路** | `cpe-link-test` | Traceroute 路径追踪和链路分流检测 | 可选：DNS + TCPing 缓存 |
| 7 | **规则分析** | `rule-analyze` | 基于证据链执行诊断规则引擎 | 证据链 JSON 文件 |
| 8 | **报告生成** | `report-gen` | 生成 HTML/JSON 可视化报告 | 证据链 JSON 文件 |
| 9 | **完整流程** | `quick-check` | 执行完整的一键体检流程 | 无（自动编排） |

---

## 🚀 快速开始

### 查看所有可用命令

```powershell
python -m sdwan_desktop.interface.cli.main --help
```

### 查看某个命令的帮助

```powershell
python -m sdwan_desktop.interface.cli.main <command> --help

# 示例
python -m sdwan_desktop.interface.cli.main dns-split-test --help
```

---

## 📖 详细使用说明

### 1️⃣ 系统信息采集 (`system-collect`)

**功能**：采集操作系统版本、网络适配器、IP 配置、路由表等系统信息。

#### 基本用法

```powershell
# 使用默认配置
python -m sdwan_desktop.interface.cli.main system-collect

# 启用详细输出
python -m sdwan_desktop.interface.cli.main system-collect --verbose
```

#### 预期输出

```text
💻 系统信息采集模块
============================================================

🚀 开始采集系统信息...
------------------------------------------------------------

============================================================
✅ 采集完成 (耗时: 0.5s)
============================================================

📊 系统信息摘要:
   - 主机名: DESKTOP-ABC123
   - OS: Windows 10 Pro 22H2
   - IP地址: 192.168.1.100
   - 子网掩码: 255.255.255.0
   - 默认网关: 192.168.1.1
   - DNS服务器: 114.114.114.114, 223.5.5.5
   - MAC地址: AA:BB:CC:DD:EE:FF
```

#### 应用场景

- ✅ 快速查看本机网络配置
- ✅ 验证默认网关和 DNS 设置
- ✅ 为后续测试提供基础数据

---

### 2️⃣ 网关连通性测试 (`gateway-test`)

**功能**：通过 ICMP Ping 测试到默认网关的连通性。

#### 基本用法

```powershell
# 使用系统默认网关
python -m sdwan_desktop.interface.cli.main gateway-test

# 指定自定义网关
python -m sdwan_desktop.interface.cli.main gateway-test -g 192.168.1.1

# 自定义 Ping 次数和超时
python -m sdwan_desktop.interface.cli.main gateway-test -g 192.168.1.1 -c 8 -t 15
```

#### 参数说明

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--gateway` | `-g` | String | 系统默认网关 | 网关 IP 地址 |
| `--count` | `-c` | Int | 4 | Ping 次数 |
| `--timeout` | `-t` | Int | 10 | 超时时间（秒） |
| `--verbose` | `-v` | Flag | False | 详细输出 |

#### 预期输出

```text
🌐 网关连通性测试模块
============================================================

🚀 开始测试网关连通性 (192.168.1.1)...
------------------------------------------------------------

============================================================
✅ 测试完成 (耗时: 1.2s)
============================================================

📊 测试结果:
   - 目标网关: 192.168.1.1
   - 状态: ✅ 可达
   - 平均RTT: 2.3ms
   - 最小RTT: 1.8ms
   - 最大RTT: 3.1ms
   - 丢包率: 0.0%
```

#### 应用场景

- ✅ 验证局域网连通性
- ✅ 排查网关故障
- ✅ 评估网络延迟

---

### 3️⃣ DNS 解析测试 (`dns-resolve`)

**功能**：测试 DNS 服务器的响应时间和解析结果。

#### 基本用法

```powershell
# 使用系统 DNS 服务器
python -m sdwan_desktop.interface.cli.main dns-resolve

# 指定自定义 DNS 服务器和域名
python -m sdwan_desktop.interface.cli.main dns-resolve \
    -d "114.114.114.114,8.8.8.8" \
    --domain www.google.com

# 启用详细输出
python -m sdwan_desktop.interface.cli.main dns-resolve --verbose
```

#### 参数说明

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--dns-servers` | `-d` | String | 系统 DNS | DNS 服务器列表（逗号分隔） |
| `--domain` | - | String | www.baidu.com | 测试域名 |
| `--verbose` | `-v` | Flag | False | 详细输出 |

#### 预期输出

```text
🔍 DNS解析测试模块
============================================================

🚀 开始测试DNS解析 (www.baidu.com)...
------------------------------------------------------------

   📡 测试DNS服务器: 114.114.114.114
      ✅ 成功, RTT=15.2ms, IPs=39.156.70.46

   📡 测试DNS服务器: 223.5.5.5
      ✅ 成功, RTT=12.8ms, IPs=39.156.70.46

============================================================
✅ 测试完成 (耗时: 0.8s)
============================================================

📊 测试结果汇总:
   - 测试DNS服务器数: 2
   - 成功数: 2
   - 失败数: 0
```

#### 应用场景

- ✅ 验证 DNS 服务器可用性
- ✅ 对比不同 DNS 服务商的解析速度
- ✅ 排查 DNS 污染问题

---

### 4️⃣ 互联网连通性测试 (`internet-test`)

**功能**：通过 TCPing 测试国内外目标的 HTTPS（443端口）连通性。

#### 基本用法

```powershell
# 使用默认统一域名集（8个域名）
python -m sdwan_desktop.interface.cli.main internet-test

# 指定自定义域名
python -m sdwan_desktop.interface.cli.main internet-test \
    -d "www.baidu.com,www.google.com,www.tiktok.com"

# 启用详细输出
python -m sdwan_desktop.interface.cli.main internet-test --verbose
```

#### 参数说明

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--domains` | `-d` | String | 统一域名集 | 测试域名列表（逗号分隔） |
| `--verbose` | `-v` | Flag | False | 详细输出 |

#### 预期输出

```text
🌍 互联网连通性测试模块
============================================================

📋 测试配置:
   - 测试域名: 8 个
     1. www.baidu.com
     2. www.taobao.com
     ...

🚀 开始执行互联网连通性测试...
------------------------------------------------------------

============================================================
✅ 测试完成 (耗时: 15.0s)
============================================================

📊 测试结果摘要:
   - 国内成功率: 4/4 (100%)
   - 国际成功率: 4/4 (100%)

📝 详细结果:

   【国内目标】
     ✅ www.baidu.com: 25.3ms
     ✅ www.taobao.com: 18.7ms
     ✅ github.com: 120.5ms
     ✅ office365.com: 95.2ms

   【国际目标】
     ✅ www.google.com: 180.3ms
     ✅ www.youtube.com: 165.8ms
     ✅ aws.amazon.com: 210.4ms
     ✅ www.aliyun.com: 22.1ms
```

#### 应用场景

- ✅ 验证跨境网络可达性
- ✅ 评估国际链路质量
- ✅ 排查防火墙阻断问题

---

### 5️⃣ DNS 分流检测 (`dns-split-test`)

**功能**：对比国内外 DNS 服务器对同一域名的解析结果，判断是否存在地域差异。

#### 基本用法

```powershell
# 使用默认配置
python -m sdwan_desktop.interface.cli.main dns-split-test

# 指定自定义域名和 DNS 服务器
python -m sdwan_desktop.interface.cli.main dns-split-test \
    -d "www.tiktok.com,www.temu.com" \
    --domestic-dns "223.5.5.5" \
    --international-dns "8.8.8.8"

# 启用详细输出
python -m sdwan_desktop.interface.cli.main dns-split-test --verbose
```

#### 参数说明

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--domains` | `-d` | String | 统一域名集 | 测试域名列表（逗号分隔） |
| `--domestic-dns` | - | String | 114.114.114.114,223.5.5.5 | 国内 DNS 服务器 |
| `--international-dns` | - | String | 8.8.8.8,1.1.1.1 | 国际 DNS 服务器 |
| `--verbose` | `-v` | Flag | False | 详细输出 |

#### 预期输出

```text
🔍 DNS 分流独立测试模块
============================================================

📋 测试配置:
   - 测试域名: 8 个
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

#### 应用场景

- ✅ 检测 CDN 智能调度
- ✅ 排查 DNS 污染
- ✅ 验证 SD-WAN DNS 策略

---

### 6️⃣ CPE 链路分流检测 (`cpe-link-test`)

**功能**：通过 Traceroute 追踪到不同目标的路径，检测 CPE 设备的链路分流情况。

#### 基本用法

```powershell
# 使用默认配置
python -m sdwan_desktop.interface.cli.main cpe-link-test

# 指定自定义域名和跳数
python -m sdwan_desktop.interface.cli.main cpe-link-test \
    -d "www.baidu.com,www.google.com" \
    -m 10 \
    --cpe-exit-hop 2

# 启用详细输出
python -m sdwan_desktop.interface.cli.main cpe-link-test --verbose
```

#### 参数说明

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--domains` | `-d` | String | 统一域名集 | 测试域名列表（逗号分隔） |
| `--max-hops` | `-m` | Int | 智能计算 | Traceroute 最大跳数 |
| `--cpe-exit-hop` | - | Int | 2 | CPE 出口跳数 |
| `--verbose` | `-v` | Flag | False | 详细输出 |

#### 预期输出

```text
🛣️ CPE链路分流检测模块
============================================================

📋 测试配置:
   - 测试域名: 8 个
   - 最大跳数: 智能计算
   - CPE出口跳数: 2

🚀 开始执行CPE链路分流检测...
------------------------------------------------------------

============================================================
✅ 测试完成 (耗时: 65.0s)
============================================================

📊 测试结果摘要:
   - 总测试域名数: 8
   - 检测到链路数: 2
   - 是否多链路分流: 是

🌐 链路分布:
   - [国内链路]: www.baidu.com, www.taobao.com, github.com, office365.com
   - [国际链路]: www.google.com, www.youtube.com, aws.amazon.com, www.aliyun.com

📝 详细路径分析（前3个域名）:

   [www.baidu.com] -> 39.156.70.46
     路径类别: 国内链路
     置信度: 0.92
     路径跳数: 7
     路径概览: 192.168.1.1 -> 10.0.0.1 -> 202.97.33.1 -> ... -> 39.156.70.46
```

#### 应用场景

- ✅ 验证 SD-WAN 策略路由
- ✅ 检测链路负载均衡
- ✅ 排查路由环路问题

---

### 7️⃣ 规则引擎分析 (`rule-analyze`)

**功能**：基于已有的证据链数据执行诊断规则分析，生成诊断结论和建议。

#### 基本用法

```powershell
# 从证据链 JSON 文件执行分析
python -m sdwan_desktop.interface.cli.main rule-analyze -i evidence.json

# 启用详细输出
python -m sdwan_desktop.interface.cli.main rule-analyze -i evidence.json --verbose
```

#### 参数说明

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--input` | `-i` | String | **必需** | 证据链 JSON 文件路径 |
| `--verbose` | `-v` | Flag | False | 详细输出 |

#### 预期输出

```text
🧠 规则引擎分析模块
============================================================

📂 加载证据链: evidence.json
   - Trace ID: 30b34855-9ac8-4f42-8eaa-16e9843b43a2

🚀 开始执行规则分析 (15条规则)...
------------------------------------------------------------

============================================================
✅ 分析完成
============================================================

📊 诊断结果摘要:
   - 整体状态: WARNING
   - 严重问题数: 0
   - 警告数: 2
   - 建议数: 3

⚠️  发现的问题:
   🟡 [WARNING] DNS解析存在地域差异
      www.baidu.com 在国内外DNS解析出不同的IP地址
   🟡 [WARNING] 国际链路延迟较高
      平均RTT超过150ms，可能影响用户体验

💡 优化建议:
   1. 检查SD-WAN DNS策略配置，确保分流规则正确
   2. 考虑增加国际链路带宽或优化路由选择
   3. 定期监控关键业务域名的连通性
```

#### 应用场景

- ✅ 离线分析历史诊断数据
- ✅ 批量处理多个证据链文件
- ✅ 集成到自动化监控系统

---

### 8️⃣ 报告生成 (`report-gen`)

**功能**：基于证据链数据生成可视化的 HTML 或 JSON 报告。

#### 基本用法

```powershell
# 生成 HTML 报告
python -m sdwan_desktop.interface.cli.main report-gen \
    -e evidence.json \
    -o report.html

# 生成 JSON 报告
python -m sdwan_desktop.interface.cli.main report-gen \
    -e evidence.json \
    -o report.json \
    --format json
```

#### 参数说明

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--evidence` | `-e` | String | **必需** | 证据链 JSON 文件路径 |
| `--output` | `-o` | String | report.html | 报告输出路径 |
| `--format` | `-f` | Choice | html | 输出格式（html/json） |

#### 预期输出

```text
📄 报告生成模块
============================================================

📂 加载证据链: evidence.json
   - Trace ID: 30b34855-9ac8-4f42-8eaa-16e9843b43a2

🚀 开始生成HTML报告...
------------------------------------------------------------

✅ HTML报告已生成: report.html
   - 文件大小: 125680 bytes

💡 提示: 在浏览器中打开 report.html 查看可视化报告
```

#### 应用场景

- ✅ 生成客户交付的诊断报告
- ✅ 存档历史诊断记录
- ✅ 分享诊断结果给团队成员

---

### 9️⃣ 完整一键体检 (`quick-check`)

**功能**：执行完整的一键体检流程，自动编排所有模块并生成报告。

#### 基本用法

```powershell
# 执行完整流程并生成 HTML 报告
python -m sdwan_desktop.interface.cli.main quick-check --output report.html

# 启用详细输出
python -m sdwan_desktop.interface.cli.main quick-check --verbose --output report.html

# 禁用并行执行（用于调试）
python -m sdwan_desktop.interface.cli.main quick-check --no-parallel
```

#### 参数说明

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--output` | `-o` | String | 自动生成 | 报告输出路径 |
| `--format` | `-f` | Choice | html | 输出格式（html/json） |
| `--verbose` | `-v` | Flag | False | 详细输出 |
| `--no-parallel` | - | Flag | False | 禁用并行执行 |

---

## 💡 最佳实践

### 场景 1：快速排查网络问题

```powershell
# 步骤1：检查网关连通性
python -m sdwan_desktop.interface.cli.main gateway-test

# 步骤2：检查 DNS 解析
python -m sdwan_desktop.interface.cli.main dns-resolve -d "114.114.114.114" --domain www.example.com

# 步骤3：检查互联网连通性
python -m sdwan_desktop.interface.cli.main internet-test -d "www.example.com"
```

### 场景 2：验证 SD-WAN 配置

```powershell
# 步骤1：检查 DNS 分流
python -m sdwan_desktop.interface.cli.main dns-split-test --verbose

# 步骤2：检查 CPE 链路分流
python -m sdwan_desktop.interface.cli.main cpe-link-test --verbose

# 步骤3：生成报告
python -m sdwan_desktop.interface.cli.main quick-check --output sdwan_report.html
```

### 场景 3：跨境电商网络诊断

```powershell
# 针对电商平台进行专项测试
python -m sdwan_desktop.interface.cli.main dns-split-test \
    -d "www.tiktok.com,www.temu.com,www.shein.com" \
    --verbose

python -m sdwan_desktop.interface.cli.main internet-test \
    -d "www.tiktok.com,www.temu.com,www.shein.com" \
    --verbose
```

### 场景 4：离线分析报告

```powershell
# 步骤1：执行完整体检并保存证据链
python -m sdwan_desktop.interface.cli.main quick-check --format json --output evidence.json

# 步骤2：稍后离线分析
python -m sdwan_desktop.interface.cli.main rule-analyze -i evidence.json --verbose

# 步骤3：重新生成报告
python -m sdwan_desktop.interface.cli.main report-gen -e evidence.json -o final_report.html
```

---

## 🔧 技术细节

### 1. 缓存机制

- **独立测试模式**：默认不使用缓存（`use_cache=False`），确保每次测试都是最新结果
- **完整流程模式**：使用缓存复用（`use_cache=True`），避免重复查询提升性能

### 2. 数据来源

所有独立测试命令直接调用 Service 层的优化方法：
- [`connectivity_tester.test_internet_optimized()`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\connectivity.py#L624-L754)
- [`dns_split_tester.test_optimized()`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py#L625-L706)
- [`dns_split_tester.test_cpe_link_routing_optimized()`](file://d:\ai-missions\deepseek\sdwan_diagnostic_platform\src\sdwan_desktop\services\dns_split.py#L1452-L1540)

### 3. 输出规范

遵循**日志层级规范**：
- **Service 层**：使用 `logger.info()` / `logger.error()`
- **CLI 层**：使用 `print()` 直接向用户展示进度和结果
- **详细模式**：通过 `--verbose` 参数控制额外信息的输出

### 4. 错误处理

所有命令都包含完善的异常处理：
- 捕获并记录详细错误信息
- 提供友好的错误提示
- 返回非零退出码标识失败状态

---

## 📝 相关文档

- [DNS 分流独立测试指南](./DNS_SPLIT_INDEPENDENT_TEST_GUIDE.md)
- [CPE 链路分流优化文档](./CPE_LINK_ROUTING_OPTIMIZATION.md)
- [一键体检优化文档](./QUICK_CHECK_OPTIMIZATION.md)
- [Traceroute 配置指南](./TRACEROUTE_HOP_CONFIGURATION_GUIDE.md)

---

**最后更新**：2026-05-02  
**维护者**：SD-WAN 诊断平台团队
