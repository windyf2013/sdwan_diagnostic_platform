# TCP端口探测CLI命令使用指南

**日期**: 2026-05-03  
**版本**: v1.0.0  
**状态**: 已实现，与GUI调用流程完全一致

---

## 📋 概述

新增独立的TCP端口探测CLI命令 `agentctl tcping`，用于快速测试目标主机端口的连通性。该命令与GUI工具Tab的tcping功能使用**完全相同的调用流程**，确保测试结果的一致性。

---

## 🚀 快速开始

### 基本用法

```bash
# 测试默认端口（80）
agentctl tcping www.github.com

# 测试指定端口
agentctl tcping www.github.com --port 443

# 简写形式
agentctl tcping www.github.com -p 443
```

### 常用示例

```bash
# 测试Web服务器（HTTPS）
agentctl tcping www.baidu.com -p 443

# 测试DNS服务器
agentctl tcping 114.114.114.114 -p 53

# 测试SSH服务
agentctl tcping 192.168.1.1 -p 22

# 自定义探测次数和超时
agentctl tcping www.google.com -p 443 -c 10 -t 3

# 详细模式显示每次探测结果
agentctl tcping www.github.com -p 443 -v
```

---

## 📖 完整参数说明

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `host` | - | str | **必填** | 目标主机IP或域名 |
| `--port` | `-p` | int | 80 | 目标端口（1-65535） |
| `--count` | `-c` | int | 4 | 探测次数（1-10） |
| `--timeout` | `-t` | int | 5 | 超时秒数（1-30） |
| `--source-ip` | - | str | None | 源IP地址（可选） |
| `--source-port` | - | int | None | 源端口（可选） |
| `--verbose` | `-v` | flag | False | 显示详细输出 |

---

## 📊 输出示例

### 成功场景

```
============================================================
🔍 TCP端口探测测试
============================================================
目标主机: www.github.com
目标端口: 443
探测次数: 4
超时时间: 5秒
开始时间: 2026-05-03 10:30:00
============================================================


============================================================
✅ 执行成功
============================================================

⏱️  耗时: 245.67 ms

📌 目标主机: www.github.com
📌 目标端口: 443
📌 解析IP: 20.205.243.166
📌 端口状态: ✅ 开放

📊 探测统计:
   - 总探测次数: 4
   - 成功次数: 4
   - 丢包率: 0.0%

⏱️  响应时间:
   - 最小: 45.20 ms
   - 平均: 48.35 ms
   - 最大: 52.10 ms
   - 标准差: 2.85 ms

============================================================
```

### 详细模式（--verbose）

```bash
agentctl tcping www.github.com -p 443 -v
```

额外显示：
```
📋 详细探测记录:
   1. ✅ 45.20 ms
   2. ✅ 48.50 ms
   3. ✅ 47.80 ms
   4. ✅ 52.10 ms
```

### 失败场景

```
============================================================
❌ 执行失败
============================================================
错误信息: 连接超时
错误代码: TOOL_TIMEOUT
============================================================
```

---

## 🔧 技术实现

### 与GUI的一致性保证

#### GUI调用流程（ToolWorker.run）
```python
# 1. 从tool_registry获取工具类
tool_class = tool_registry.get_tool("tcping")

# 2. 创建ToolRequest
request = ToolRequest(tool_name="tcping", parameters=params)

# 3. 创建FlowContext
ctx = FlowContext(flow_id="gui-session", flow_name="gui-tool-execution")

# 4. 实例化工具并执行
tool_instance = tool_class()
result = loop.run_until_complete(tool_instance.execute(request, ctx))

# 5. 转换为JSON字典
result_dict = result.to_json_dict()
```

#### CLI调用流程（tcping_test命令）
```python
# ✅ 完全相同的步骤
tool_class = tool_registry.get_tool("tcping")
request = ToolRequest(tool_name="tcping", parameters=params)
ctx = FlowContext(flow_id="cli-tcping-test", flow_name="cli-tcping-execution")
tool_instance = tool_class()
result = loop.run_until_complete(tool_instance.execute(request, ctx))
result_dict = result.to_json_dict()
```

### 关键一致性要点

| 检查项 | GUI | CLI | 是否一致 |
|--------|-----|-----|---------|
| **工具注册** | `tool_registry.get_tool()` | `tool_registry.get_tool()` | ✅ 相同 |
| **请求对象** | `ToolRequest(tool_name, params)` | `ToolRequest(tool_name, params)` | ✅ 相同 |
| **上下文对象** | `FlowContext(flow_id, flow_name)` | `FlowContext(flow_id, flow_name)` | ✅ 相同 |
| **工具实例化** | `tool_class()` | `tool_class()` | ✅ 相同 |
| **执行方法** | `tool_instance.execute(request, ctx)` | `tool_instance.execute(request, ctx)` | ✅ 相同 |
| **结果转换** | `result.to_json_dict()` | `result.to_json_dict()` | ✅ 相同 |
| **异步事件循环** | `asyncio.new_event_loop()` | `asyncio.new_event_loop()` | ✅ 相同 |

---

## 🎯 使用场景

### 1. 快速诊断网络问题

```bash
# 检查Web服务是否可达
agentctl tcping example.com -p 443

# 检查数据库服务
agentctl tcping db-server.local -p 3306

# 检查Redis缓存
agentctl tcping redis-server.local -p 6379
```

### 2. 验证防火墙规则

```bash
# 测试特定端口是否被阻止
agentctl tcping firewall-test.example.com -p 8080

# 如果返回"端口关闭"，可能是防火墙阻止
```

### 3. 性能基准测试

```bash
# 多次探测获取平均响应时间
agentctl tcping cdn.example.com -p 443 -c 20 -v

# 分析响应时间的稳定性（标准差）
```

### 4. 服务健康检查

```bash
# 在脚本中集成
if agentctl tcping api.example.com -p 443 | grep -q "✅ 开放"; then
    echo "API服务正常"
else
    echo "API服务异常"
fi
```

---

## 📝 与其他工具的对比

| 工具 | 协议 | 用途 | 优势 |
|------|------|------|------|
| **tcping** | TCP | 端口连通性测试 | ✅ 精确测量TCP握手时间<br>✅ 不受ICMP限制<br>✅ 可测试任意端口 |
| **ping** | ICMP | 主机可达性测试 | ✅ 简单快速<br>✅ 广泛支持 |
| **dns** | DNS | 域名解析测试 | ✅ 验证DNS配置<br>✅ 检测DNS劫持 |
| **traceroute** | ICMP/UDP | 路径追踪 | ✅ 显示完整路由<br>✅ 定位网络瓶颈 |

---

## ⚠️ 注意事项

### 1. 端口范围限制
```bash
# ❌ 错误：端口超出范围
agentctl tcping example.com -p 0
agentctl tcping example.com -p 70000

# ✅ 正确：端口在1-65535范围内
agentctl tcping example.com -p 443
```

### 2. 探测次数限制
```bash
# ❌ 错误：次数超出范围
agentctl tcping example.com -p 443 -c 0
agentctl tcping example.com -p 443 -c 15

# ✅ 正确：次数在1-10范围内
agentctl tcping example.com -p 443 -c 4
```

### 3. 超时设置建议
```bash
# 本地网络：较短超时
agentctl tcping 192.168.1.1 -p 80 -t 2

# 国际网络：较长超时
agentctl tcping www.google.com -p 443 -t 10
```

### 4. 权限要求
- ✅ 普通用户即可执行（不需要root/admin权限）
- ✅ 使用TCP连接，不依赖ICMP权限

---

## 🔍 故障排查

### 问题1: 命令未找到

```bash
# 检查是否已安装
which agentctl

# 如果未找到，重新安装包
pip install -e .
```

### 问题2: 所有探测都超时

**可能原因**：
1. 目标主机不可达
2. 防火墙阻止了TCP连接
3. 目标端口未开放

**排查步骤**：
```bash
# 1. 检查主机是否可达
ping example.com

# 2. 尝试其他端口
agentctl tcping example.com -p 80
agentctl tcping example.com -p 443

# 3. 增加超时时间
agentctl tcping example.com -p 443 -t 10
```

### 问题3: 解析IP失败

```bash
# 检查DNS配置
nslookup example.com

# 直接使用IP测试
agentctl tcping 93.184.216.34 -p 443
```

---

## 📚 相关文档

- [TCP端口探测工具实现](../src/sdwan_desktop/tools/implementations/network/tcping.py)
- [CLI主命令组](../src/sdwan_desktop/interface/cli/main.py)
- [GUI工具Tab实现](../src/sdwan_desktop/interface/gui/tabs/tools_tab.py)
- [工具系统规范](../docs/SDWAN_SPEC.md#24-工具系统)

---

## 🎯 总结

### 核心优势
1. ✅ **与GUI完全一致**：使用相同的调用流程和参数
2. ✅ **独立测试**：无需启动GUI即可快速测试
3. ✅ **灵活配置**：支持自定义端口、次数、超时等参数
4. ✅ **详细输出**：支持verbose模式查看每次探测结果
5. ✅ **易于集成**：可在脚本中自动化调用

### 适用场景
- 🔧 网络工程师快速诊断端口连通性
- 🧪 开发人员调试网络服务
- 📊 运维人员监控服务可用性
- 🎓 学习者理解TCP连接过程

### 下一步优化建议
1. 添加JSON输出格式支持（`--json`）
2. 支持批量测试多个端口（`--ports 80,443,8080`）
3. 添加历史记录功能（保存测试结果）
4. 集成到一键体检流程中
