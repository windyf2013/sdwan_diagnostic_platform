# CPE链路路由追踪超时修复（2026-05-03）

## 问题描述

用户运行CLI quick-check命令后，HTML报告中缺少CPE链路路由追踪（Traceroute）数据。

## 根本原因分析

通过分析`run_log.txt`日志文件，发现以下问题：

### 1. TCPing探测耗时过长
- **现象**：对不可达目标（google.com、youtube.com、tiktok.com）的TCPing探测耗时40+秒
- **原因**：
  - TCPing工具配置：count=2, timeout=3秒，ToolRequest超时=8秒
  - retry_count=1，超时后会重试1次
  - 实际执行时，每次TCPing探测耗时约20秒（8秒超时 + 重试）
  - 2个端口（443和80）总计约40秒

### 2. CPE测试总超时不足
- **Flow层超时**：70秒
- **CLI内部超时**：60秒
- **实际耗时**：4个域名并发执行，最慢的耗时超过60秒，导致测试被强制中断

### 3. Traceroute被跳过
- www.baidu.com: TCPing成功（约41秒），执行了Traceroute ✅
- www.google.com: TCPing失败（约43秒），跳过Traceroute ❌
- www.youtube.com: TCPing失败（约42秒），跳过Traceroute ❌
- www.tiktok.com: TCPing失败（约41秒），跳过Traceroute ❌

由于只有1个域名执行了Traceroute，且CPE测试在60秒时超时，导致最终结果中domain_results为空或不完整。

## 修复方案

### 1. 优化TCPing超时配置（dns_split.py）

降低CPE测试中TCPing的超时时间，让不可达目标快速失败：

```python
# 修改前
tcping_request_443 = ToolRequest(
    tool_name="tcping",
    parameters={
        "host": path_result.resolved_ip,
        "port": 443,
        "count": 2,      # 探测2次
        "timeout": 3     # 单次超时3秒
    },
    timeout_seconds=8,   # 总超时8秒
    trace_id=ctx.trace_id
)

# 修改后
tcping_request_443 = ToolRequest(
    tool_name="tcping",
    parameters={
        "host": path_result.resolved_ip,
        "port": 443,
        "count": 1,      # ✅ 减少探测次数：从2次降至1次
        "timeout": 2     # ✅ 降低单次超时：从3秒降至2秒
    },
    timeout_seconds=5,   # ✅ 降低总超时：从8秒降至5秒
    trace_id=ctx.trace_id
)
```

**效果**：
- 单个端口探测耗时从约20秒降至约5秒
- 2个端口总计约10秒（而非40秒）
- 大幅缩短不可达目标的判断时间

### 2. 调整超时配置

#### Flow层超时（quick_check.py）
```python
# 修改前
timeout_seconds=70

# 修改后
timeout_seconds=90  # ✅ 优化：增加超时时间，适配TCPing快速失败策略（4域名×2端口×5秒+Traceroute+缓冲≈80秒）
```

#### CLI内部超时（quick_check.py）
```python
# 修改前
timeout=60

# 修改后
timeout=80  # ✅ 优化：增加超时时间，适配TCPing快速失败策略
```

#### GUI内部超时（quick_check_tab.py）
```python
# 修改前
timeout=60

# 修改后
timeout=80  # ✅ 优化：增加超时时间，适配TCPing快速失败策略
```

## 预期效果

修复后，CPE测试的预计耗时：
- DNS解析：已完成（复用缓存）
- TCPing探测：4域名 × 2端口 × 5秒 = 40秒（并发执行，实际约10-15秒）
- Traceroute执行：可达域名执行，约10-20秒
- 总耗时：约30-40秒（远低于90秒超时限制）

## 验证方法

重新运行CLI quick-check命令：
```bash
agentctl quick-check --output test_report.html
```

检查终端输出：
1. 是否显示"✓ (XX.Xs)"而非"✗ (60.0s) - 测试超时"
2. 是否显示CPE链路分流的统计信息
3. 是否有域名执行了Traceroute

检查HTML报告：
1. "业务路径路由追踪"章节是否显示完整的路径信息
2. 是否有traceroute跳点数据

## 影响范围

- `src/sdwan_desktop/services/dns_split.py`: _analyze_domain_path函数中的TCPing配置
- `src/sdwan_desktop/interface/cli/commands/quick_check.py`: step_cpe_link_routing的内部超时
- `src/sdwan_desktop/interface/gui/tabs/quick_check_tab.py`: step_cpe_link_routing的内部超时
- `src/sdwan_desktop/flow/definitions/quick_check.py`: step-cpe-link-routing的Flow层超时

## 注意事项

1. **TCPing探测次数减少**：从2次降至1次，可能略微降低测量精度，但大幅提升速度
2. **超时时间增加**：Flow层从70秒增至90秒，整体流程耗时略有增加，但在可接受范围内
3. **兼容性**：此修复同时适用于CLI和GUI，保持两者行为一致
