# 一键体检模块独立测试指南

## 概述

为了便于调试和验证一键体检流程中的各个模块，我们为每个关键步骤创建了独立的CLI测试命令。这使得您可以：

- ✅ 快速定位问题所在的模块
- ✅ 单独测试某个功能而不需要运行完整流程
- ✅ 对比不同配置参数的效果
- ✅ 集成到自动化测试脚本中

## 已实现的独立测试命令

### 1. system-collect - 系统信息采集

**功能**: 采集Windows网络配置信息，包括网卡、路由、DNS等。

**使用示例**:
```bash
# 基本用法
python -m sdwan_desktop.interface.cli.main system-collect

# 详细输出模式
python -m sdwan_desktop.interface.cli.main system-collect --verbose

# 保存结果到JSON文件
python -m sdwan_desktop.interface.cli.main system-collect --verbose -o snapshot.json
```

**输出内容**:
- 网卡数量及详细信息
- 主网卡状态（连接状态、IP地址、网关、DNS）
- IP配置信息

---

### 2. gateway-test - 网关连通性测试

**功能**: 测试默认网关的可达性和延迟。

**使用示例**:
```bash
# 自动检测网关并测试
python -m sdwan_desktop.interface.cli.main gateway-test

# 指定网关IP
python -m sdwan_desktop.interface.cli.main gateway-test -g 192.168.1.1

# 自定义Ping次数和超时时间
python -m sdwan_desktop.interface.cli.main gateway-test -g 192.168.1.1 -c 10 -t 15

# 详细输出
python -m sdwan_desktop.interface.cli.main gateway-test --verbose
```

**参数说明**:
- `-g, --gateway`: 网关IP地址（默认自动检测）
- `-c, --count`: Ping次数（默认4次）
- `-t, --timeout`: 超时时间（秒，默认10秒）
- `-v, --verbose`: 详细输出模式

**输出内容**:
- 网关可达性状态
- RTT统计（平均、最小、最大）
- 丢包率

---

### 3. dns-resolve - DNS解析测试

**功能**: 测试DNS服务器的解析能力和响应时间。

**使用示例**:
```bash
# 使用默认配置
python -m sdwan_desktop.interface.cli.main dns-resolve

# 指定DNS服务器和测试域名
python -m sdwan_desktop.interface.cli.main dns-resolve -d "114.114.114.114,8.8.8.8" -D www.google.com

# 自定义查询次数
python -m sdwan_desktop.interface.cli.main dns-resolve -d "114.114.114.114" -c 5 -t 10
```

**参数说明**:
- `-d, --dns-servers`: DNS服务器列表（逗号分隔，默认114.114.114.114,8.8.8.8）
- `-D, --domain`: 测试域名（默认www.baidu.com）
- `-c, --count`: 每个DNS的查询次数（默认2次）
- `-t, --timeout`: 超时时间（秒，默认5秒）

**输出内容**:
- 每个DNS服务器的响应状态
- 解析结果（IP地址）
- RTT统计

---

### 4. internet-test - 互联网连通性测试

**功能**: 测试国内外域名的TCP连通性（443端口）。

**使用示例**:
```bash
# 使用预设域名集
python -m sdwan_desktop.interface.cli.main internet-test

# 指定测试域名
python -m sdwan_desktop.interface.cli.main internet-test -D "www.baidu.com,www.google.com,www.github.com"

# 禁用缓存（强制重新探测）
python -m sdwan_desktop.interface.cli.main internet-test --no-cache

# 详细输出
python -m sdwan_desktop.interface.cli.main internet-test --verbose
```

**参数说明**:
- `-D, --domains`: 测试域名列表（逗号分隔，默认使用预设域名集）
- `--no-cache`: 禁用缓存
- `-v, --verbose`: 详细输出模式

**输出内容**:
- 国内域名成功率
- 国际域名成功率
- 各域名的连通性状态和RTT

---

### 5. dns-split-test - DNS分流测试

**功能**: 对比国内外DNS对同一域名的解析结果差异。

**使用示例**:
```bash
# 使用预设域名集
python -m sdwan_desktop.interface.cli.main dns-split-test

# 指定测试域名
python -m sdwan_desktop.interface.cli.main dns-split-test -D "www.google.com,www.baidu.com"

# 自定义DNS服务器
python -m sdwan_desktop.interface.cli.main dns-split-test \
  --domestic-dns "114.114.114.114" \
  --international-dns "8.8.8.8,1.1.1.1"

# 详细输出
python -m sdwan_desktop.interface.cli.main dns-split-test --verbose
```

**参数说明**:
- `-D, --domains`: 测试域名列表（逗号分隔）
- `--domestic-dns`: 国内DNS服务器（逗号分隔，默认从系统获取）
- `--international-dns`: 国际DNS服务器（逗号分隔，默认8.8.8.8,1.1.1.1）
- `--no-cache`: 禁用缓存
- `-v, --verbose`: 详细输出模式

**输出内容**:
- 分流统计（存在分流的域名数量）
- 每个存在分流的域名的详细对比
  - 国内DNS解析结果
  - 国际DNS解析结果
  - 分流说明

---

### 6. cpe-link-test - CPE链路分流检测

**功能**: 通过Traceroute检测CPE设备对不同域名的链路分流情况。

**使用示例**:
```bash
# 使用预设域名集
python -m sdwan_desktop.interface.cli.main cpe-link-test

# 指定测试域名和最大跳数
python -m sdwan_desktop.interface.cli.main cpe-link-test \
  -D "www.baidu.com,www.google.com" \
  -m 15

# 自定义CPE出口跳点
python -m sdwan_desktop.interface.cli.main cpe-link-test --cpe-exit-hop 3

# 详细输出
python -m sdwan_desktop.interface.cli.main cpe-link-test --verbose
```

**参数说明**:
- `-D, --domains`: 测试域名列表（逗号分隔）
- `-m, --max-hops`: Traceroute最大跳数（默认自动识别）
- `--cpe-exit-hop`: CPE出口跳点（默认2）
- `--no-cache`: 禁用缓存
- `-v, --verbose`: 详细输出模式

**注意事项**:
- 此测试耗时较长（每个域名约30秒）
- 建议先用少量域名测试

**输出内容**:
- 检测到的链路数量
- 每条链路的指纹和包含的域名
- 多链路分流详情

---

### 7. rule-analyze - 规则分析测试

**功能**: 基于证据链数据进行规则匹配和异常检测。

**使用示例**:
```bash
python -m sdwan_desktop.interface.cli.main rule-analyze -e evidence.json
```

**参数说明**:
- `-e, --evidence`: 证据链JSON文件路径（必需）
- `-v, --verbose`: 详细输出模式

**注意**: 当前为占位实现，完整的离线分析功能需要进一步开发。

---

### 8. report-gen - 报告生成测试

**功能**: 基于证据链数据生成HTML或JSON报告。

**使用示例**:
```bash
# 生成HTML报告
python -m sdwan_desktop.interface.cli.main report-gen -e evidence.json -o report.html

# 生成JSON报告
python -m sdwan_desktop.interface.cli.main report-gen -e evidence.json -o report.json --format json
```

**参数说明**:
- `-e, --evidence`: 证据链JSON文件路径（必需）
- `-o, --output`: 报告输出路径（默认report.html）
- `-f, --format`: 输出格式（html或json，默认html）

**注意**: HTML报告生成通常需要完整的DiagnosisResult对象，当前仅支持在线流程中的实时报告生成。

---

## 快速验证脚本

我们还提供了一个快速验证脚本，可以直接测试各个模块的功能：

```bash
# 运行快速验证（测试前4个模块）
python quick_verify.py

# 运行完整测试（包括所有CLI命令）
python test_independent_commands.py
```

## 故障排查

### 常见问题

1. **命令找不到**
   - 确保在项目根目录下执行
   - 检查是否正确安装了依赖包

2. **权限错误**
   - Windows下可能需要以管理员身份运行（特别是traceroute相关命令）

3. **超时错误**
   - 增加`--timeout`参数值
   - 检查网络连接是否正常

4. **DNS解析失败**
   - 尝试更换DNS服务器
   - 检查防火墙设置

### 调试技巧

- 使用`--verbose`参数查看详细日志
- 先用简单命令测试（如system-collect），再测试复杂命令
- 查看错误信息和堆栈跟踪定位问题

## 下一步

如果独立测试命令都能正常运行，但一键体检流程仍有问题，请：

1. 运行完整的一键体检流程，记录错误信息
2. 根据错误信息，使用对应的独立测试命令进行排查
3. 对比独立测试和流程中的表现，找出差异

---

**最后更新**: 2026-05-02
