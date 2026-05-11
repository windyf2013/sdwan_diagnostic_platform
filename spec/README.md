# SD-WAN 诊断平台规范索引

## 📚 规范文档导航

本文档提供所有技术规范、配置标准和最佳实践的索引，帮助开发者快速定位所需信息。

---

## 🔍 按功能模块分类

### 1️⃣ Traceroute / 路径追踪 ⭐

#### 核心规范
- **[20_domain/probe/probe_traceroute.md](20_domain/probe/probe_traceroute.md)** ⭐⭐ **必读**
  - 📏 标准配置：7跳 × 3次 × 5秒 = 105秒
  - 🔢 计算公式和超时层级设计
  - ⚙️ Flow层和服务层配置示例
  - 🛠️ 实现要求和数据模型
  - 📊 场景化配置对比

#### 实施指南
- [../docs/TRACEROUTE_HOP_CONFIGURATION_GUIDE.md](../docs/TRACEROUTE_HOP_CONFIGURATION_GUIDE.md) - 详细的场景分析和智能配置算法
- [../docs/TRACEROUTE_EMPTY_PATH_FIX.md](../docs/TRACEROUTE_EMPTY_PATH_FIX.md) - 空路径问题修复
- [../docs/TRACEROUTE_PATH_DISPLAY_ENHANCEMENT.md](../docs/TRACEROUTE_PATH_DISPLAY_ENHANCEMENT.md) - 路径显示增强
- [../docs/TRACEROUTE_PROCESS_VARIABLE_FIX.md](../docs/TRACEROUTE_PROCESS_VARIABLE_FIX.md) - 进程变量修复
- [../docs/TRACEROUTE_TIMEOUT_HOP_DISPLAY.md](../docs/TRACEROUTE_TIMEOUT_HOP_DISPLAY.md) - 超时跳点显示
- [../docs/WINDOWS_TRACERT_MISSING_HOPS_FIX.md](../docs/WINDOWS_TRACERT_MISSING_HOPS_FIX.md) - Windows缺失跳点修复

#### 相关服务实现
- `src/sdwan_desktop/services/dns_split.py` - DNS分流和CPE链路检测（包含Traceroute调用）
- `src/sdwan_desktop/tools/implementations/network/traceroute.py` - Traceroute工具实现

---

### 2️⃣ ICMP / Ping 探测

#### 核心规范
- **[20_domain/probe/probe_icmp.md](20_domain/probe/probe_icmp.md)** ⭐⭐ **必读**
  - 📏 ICMP协议标准
  - 🔧 探测参数和数据模型
  - 🛠️ 实现要求和平台兼容性
  - 📊 性能要求和安全考虑

#### 相关服务实现
- `src/sdwan_desktop/services/connectivity.py` - 连通性测试服务
- `src/sdwan_desktop/tools/implementations/network/ping.py` - Ping工具实现

---

### 3️⃣ DNS 解析与分流

#### 核心规范
- **[20_domain/probe/probe_dns.md](20_domain/probe/probe_dns.md)** ⭐⭐ **必读**
  - 📏 DNS协议标准
  - 🔧 解析参数和数据模型
  - 🛠️ 实现要求和缓存策略

#### DNS分流测试
- [../docs/DNS_SPLIT_INDEPENDENT_TEST_GUIDE.md](../docs/DNS_SPLIT_INDEPENDENT_TEST_GUIDE.md) - DNS分流独立测试指南
- [../docs/DNS_SPLIT_AND_PATH_DISPLAY_FIX.md](../docs/DNS_SPLIT_AND_PATH_DISPLAY_FIX.md) - DNS分流和路径显示修复
- [../docs/DNS_SPLIT_DISPLAY_FIX.md](../docs/DNS_SPLIT_DISPLAY_FIX.md) - DNS分流显示修复
- [../docs/dns_split_timeout_fix.md](../docs/dns_split_timeout_fix.md) - DNS分流超时修复
- [../docs/DNS_SPLIT_FIX_20260502.md](../docs/DNS_SPLIT_FIX_20260502.md) ⭐ **最新修复**

#### 相关服务实现
- `src/sdwan_desktop/services/dns_split.py` - DNS分流测试服务
- `src/sdwan_desktop/interface/cli/commands/quick_check.py` - CLI命令实现

---

### 4️⃣ TCP 端口探测

#### 核心规范
- **[20_domain/probe/probe_tcp.md](20_domain/probe/probe_tcp.md)** ⭐⭐ **必读**
  - 📏 TCP协议标准
  - 🔧 探测参数和数据模型
  - 🛠️ 实现要求和并发控制

#### 相关服务实现
- `src/sdwan_desktop/tools/implementations/network/tcping.py` - TCPing工具实现

---

### 5️⃣ CPE 链路路由检测

#### 优化文档
- [../docs/CPE_LINK_ROUTING_OPTIMIZATION.md](../docs/CPE_LINK_ROUTING_OPTIMIZATION.md) - CPE链路路由优化
- [../docs/CPE_LINK_ROUTING_PERFORMANCE_OPTIMIZATION.md](../docs/CPE_LINK_ROUTING_PERFORMANCE_OPTIMIZATION.md) - 性能优化
- [../docs/CPE_LINK_ROUTING_TCPING_OPTIMIZATION.md](../docs/CPE_LINK_ROUTING_TCPING_OPTIMIZATION.md) - TCPing优化
- [../docs/CPE_LINK_ROUTING_DNS_FIX_SUMMARY.md](../docs/CPE_LINK_ROUTING_DNS_FIX_SUMMARY.md) - DNS修复总结
- [../docs/cpe_link_routing_and_tools_output_fix.md](../docs/cpe_link_routing_and_tools_output_fix.md) - 工具和输出修复
- [../docs/cpe_link_routing_dns_failure_optimization.md](../docs/cpe_link_routing_dns_failure_optimization.md) - DNS失败优化

#### 相关服务实现
- `src/sdwan_desktop/services/dns_split.py` - CpeLinkRouteResult数据模型和检测方法

---

### 6️⃣ Flow 引擎与执行流程

#### 核心规范
- **[SDWAN_SPEC.md](SDWAN_SPEC.md)** ⭐⭐⭐ **核心规范**
  - 🏗️ 架构分层和职责划分
  - 📊 数据契约和类型定义
  - 🔄 Flow引擎和执行模型
  - 🛠️ 工具系统规范
  
- **[50_execution/pipeline_engine.md](50_execution/pipeline_engine.md)** - Pipeline引擎规范

#### 实施计划
- [sprint3_plan.md](sprint3_plan.md) - Sprint 3 计划
- [sprint4_plan.md](sprint4_plan.md) - Sprint 4 计划
- [sprint5_plan.md](sprint5_plan.md) - Sprint 5 计划
- [sprint6_plan.md](sprint6_plan.md) - Sprint 6 计划
- [sprint7_plan.md](sprint7_plan.md) - Sprint 7 计划
- [sprint8_plan.md](sprint8_plan.md) - Sprint 8 计划
- [sprint9_project_closure_plan.md](sprint9_project_closure_plan.md) - Sprint 9 项目收尾计划

#### 相关实现
- `src/sdwan_desktop/runtime/engine.py` - Flow引擎核心
- `src/sdwan_desktop/runtime/executor.py` - Step执行器
- `src/sdwan_desktop/flow/definitions/` - Flow定义

---

### 7️⃣ 数据契约与类型系统

#### 核心规范
- **[00_core/data_contract.md](00_core/data_contract.md)** - 数据契约规范
- **[00_core/state_context.md](00_core/state_context.md)** - 状态上下文规范
- **[00_core/error_model.md](00_core/error_model.md)** - 错误模型规范

#### 相关实现
- `src/sdwan_desktop/core/types/` - 类型定义
- `src/sdwan_desktop/core/errors/` - 错误定义

---

### 8️⃣ 架构与分层模型

#### 核心规范
- **[10_architecture/layering_model.md](10_architecture/layering_model.md)** - 分层架构模型

#### 相关实现
- `src/sdwan_desktop/interface/` - Interface Layer
- `src/sdwan_desktop/services/` - Service Layer
- `src/sdwan_desktop/tools/` - Tool Layer
- `src/sdwan_desktop/core/` - Core Layer

---

### 9️⃣ 报告生成

#### 核心规范
- **[20_domain/reporting/report_schema.md](20_domain/reporting/report_schema.md)** - 报告Schema规范

#### 相关实现
- `src/sdwan_desktop/reporting/` - 报告生成模块
- `src/sdwan_desktop/services/reporter/` - 报告服务

---

### 🔟 一键体检流程

#### 独立测试命令
- [../docs/INDEPENDENT_TEST_COMMANDS_GUIDE.md](../docs/INDEPENDENT_TEST_COMMANDS_GUIDE.md) - 独立测试命令使用指南
- [../QUICK_START_INDEPENDENT_TESTS.md](../QUICK_START_INDEPENDENT_TESTS.md) - 快速开始指南
- [../IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) - 实施总结

#### 修复记录
- [../docs/QUICK_CHECK_CRITICAL_FIX.md](../docs/QUICK_CHECK_CRITICAL_FIX.md) - 关键修复
- [../docs/QUICK_CHECK_FLOW_CHAIN_REVIEW.md](../docs/QUICK_CHECK_FLOW_CHAIN_REVIEW.md) - Flow链审查
- [../docs/QUICK_CHECK_OPTIMIZATION.md](../docs/QUICK_CHECK_OPTIMIZATION.md) - 优化记录
- [../docs/QUICK_CHECK_ANALYZER_REFACTORING.md](../docs/QUICK_CHECK_ANALYZER_REFACTORING.md) - 分析器重构

#### 相关实现
- `src/sdwan_desktop/flow/definitions/quick_check.py` - Quick Check Flow定义
- `src/sdwan_desktop/interface/cli/commands/quick_check.py` - CLI命令实现
- `src/sdwan_desktop/interface/gui/tabs/quick_check_tab.py` - GUI实现

---

## 🎯 按开发阶段分类

### Phase 1: 基础架构
- [SDWAN_SPEC.md](SDWAN_SPEC.md) - 核心规范
- [00_core/](00_core/) - 数据契约
- [10_architecture/](10_architecture/) - 架构模型

### Phase 2: 探针实现
- [20_domain/probe/probe_icmp.md](20_domain/probe/probe_icmp.md) - ICMP探测
- [20_domain/probe/probe_dns.md](20_domain/probe/probe_dns.md) - DNS探测
- [20_domain/probe/probe_tcp.md](20_domain/probe/probe_tcp.md) - TCP探测
- [20_domain/probe/probe_traceroute.md](20_domain/probe/probe_traceroute.md) - Traceroute探测

### Phase 3: Flow引擎
- [50_execution/pipeline_engine.md](50_execution/pipeline_engine.md) - Pipeline引擎
- [SDWAN_SPEC_PATCHES.md](SDWAN_SPEC_PATCHES.md) - 规范补丁

### Phase 4: 业务逻辑
- [detail_function_design.md](detail_function_design.md) - 详细功能设计
- [sdwan_analyzer_project.md](sdwan_analyzer_project.md) - 项目总体设计

### Phase 5: 报告与输出
- [20_domain/reporting/report_schema.md](20_domain/reporting/report_schema.md) - 报告Schema

---

## 💡 使用建议

### 对于Agent开发者

1. **实现Traceroute功能时**：
   - 📖 首先阅读：[20_domain/probe/probe_traceroute.md](20_domain/probe/probe_traceroute.md)
   - 🔧 参考标准配置：7跳 × 3次 × 5秒 = 105秒
   - 🛠️ 查看实施指南：[../docs/TRACEROUTE_HOP_CONFIGURATION_GUIDE.md](../docs/TRACEROUTE_HOP_CONFIGURATION_GUIDE.md)

2. **实现其他探针时**：
   - 📖 阅读对应的probe规范文档
   - 🔧 遵循数据模型定义
   - 🛠️ 参考现有实现代码

3. **开发Flow步骤时**：
   - 📖 阅读[SDWAN_SPEC.md](SDWAN_SPEC.md)的Flow引擎章节
   - 🔧 遵循分层架构原则
   - 🛠️ 参考现有的Flow定义

### 对于维护者

1. **查找修复记录**：
   - 使用关键词搜索 `../docs/*FIX*.md`
   - 查看最新的修复日期

2. **了解架构演进**：
   - 阅读Sprint计划文档
   - 查看规范补丁文档

3. **性能优化参考**：
   - 查看各模块的OPTIMIZATION文档
   - 参考最佳实践章节

---

## 📋 规范优先级

| 优先级 | 标识 | 说明 | 示例 |
|--------|------|------|------|
| **P0** | ⭐⭐⭐ | 核心规范，必须遵守 | SDWAN_SPEC.md |
| **P1** | ⭐⭐ | 重要规范，强烈建议 | probe_*.md |
| **P2** | ⭐ | 参考规范，建议遵循 | 实施指南、修复记录 |

---

## 🔄 更新记录

| 日期 | 版本 | 更新内容 | 作者 |
|------|------|---------|------|
| 2026-05-02 | v1.0 | 初始版本，添加Traceroute规范索引 | SD-WAN团队 |

---

**最后更新**: 2026-05-02  
**维护者**: SD-WAN 诊断平台团队  
**反馈渠道**: 提交Issue或联系技术负责人
