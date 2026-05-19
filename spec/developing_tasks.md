# SD-WAN诊断平台 - 开发任务分解

**文档版本**: v1.0.0  
**创建日期**: 2026-04-20  
**关联文档**: 项目实施方案.md / 详细设计说明.md  
**预计总工时**: 320h (8周 × 2人)

---

## 目录

1. [迭代总体规划](#1-迭代总体规划)
2. [Sprint 1: 基础框架搭建](#2-sprint-1-基础框架搭建)
3. [Sprint 2: 网络工具集](#3-sprint-2-网络工具集)
4. [Sprint 3: 一键体检](#4-sprint-3-一键体检)
5. [Sprint 4: 深度诊断](#5-sprint-4-深度诊断)
6. [Sprint 5: 业务监测](#6-sprint-5-业务监测)
7. [Sprint 6: GUI与报告](#7-sprint-6-gui与报告)
8. [Sprint 7: 集成测试与优化](#8-sprint-7-集成测试与优化)
9. [Sprint 8: 发布准备](#9-sprint-8-发布准备)
10. [附录: 任务依赖关系图](#附录-任务依赖关系图)

---

## 1. 迭代总体规划

### 1.1 迭代周期

| Sprint | 名称 | 周期 | 目标 | 交付物 |
|--------|------|------|------|--------|
| Sprint 1 | 基础框架搭建 | 第1周 | 项目骨架、核心契约、日志系统 | 可运行的CLI骨架 |
| Sprint 2 | 网络工具集 | 第2周 | 全部网络探测工具 | 7个工具+注册中心 |
| Sprint 3 | 一键体检 | 第3-4周 | 完整QuickCheck功能 | 一键体检+基础报告 |
| Sprint 4 | 深度诊断 | 第5-6周 | CPE采集+拓扑+根因分析 | 深度诊断+专业报告 |
| Sprint 5 | 业务监测 | 第7周 | Waterfall功能 | HAR采集+时序图报告 |
| Sprint 6 | GUI与报告 | 第8周 | PySide6界面+HTML模板 | 完整GUI应用 |
| Sprint 7 | 集成测试 | 第9周 | 端到端测试+性能优化 | 测试报告 |
| Sprint 8 | 发布准备 | 第10周 | 打包+文档+发布 | 安装包+用户手册 |

### 1.2 团队配置

| 角色 | 人数 | 主要职责 |
|------|------|---------|
| 后端开发 | 1人 | Flow引擎、Service层、Tool层实现 |
| 全栈开发 | 1人 | GUI界面、HTML报告模板、打包发布 |

### 1.3 任务状态标记

| 标记 | 含义 |
|------|------|
| ⬜ TODO | 待开始 |
| 🔄 IN_PROGRESS | 进行中 |
| ✅ DONE | 已完成 |
| 🚫 BLOCKED | 阻塞中 |
| 🔁 REVIEW | 待评审 |

---

## 2. Sprint 1: 基础框架搭建

**周期**: 第1周 (40h)  
**目标**: 建立符合规范的项目骨架，实现核心数据契约和日志系统

### 2.1 任务清单

| ID | 任务 | 负责人 | 预估工时 | 依赖 | 状态 | 交付物 |
|----|------|--------|---------|------|------|--------|
| 1.1 | 项目初始化 | 后端 | 2h | - | ⬜ | pyproject.toml, 目录结构 |
| 1.2 | 核心数据契约实现 | 后端 | 8h | 1.1 | ⬜ | base.py, diagnosis.py, probe.py |
| 1.3 | 错误码体系实现 | 后端 | 4h | 1.2 | ⬜ | errors/, error_codes.py |
| 1.4 | Context上下文实现 | 后端 | 4h | 1.2 | ⬜ | context.py, flow_state.py |
| 1.5 | 日志系统实现 | 后端 | 4h | 1.2 | ⬜ | logger.py, sensitive_filter.py |
| 1.6 | 配置管理实现 | 后端 | 4h | 1.1 | ⬜ | settings.py, loader.py |
| 1.7 | CLI骨架搭建 | 后端 | 4h | 1.6 | ⬜ | main.py, commands.py |
| 1.8 | 单元测试框架 | 后端 | 4h | 1.2-1.6 | ⬜ | conftest.py, 基础测试用例 |
| 1.9 | Pre-commit配置 | 后端 | 2h | 1.1 | ⬜ | .pre-commit-config.yaml |
| 1.10 | CI配置(GitHub Actions) | 后端 | 4h | 1.9 | ⬜ | .github/workflows/ci.yml |

### 2.2 验收标准

- [ ] `agentctl --version` 可正常执行
- [ ] `agentctl --help` 显示子命令列表
- [ ] 所有dataclass可通过mypy类型检查
- [ ] 日志输出包含trace_id
- [ ] Pre-commit钩子正常工作
- [ ] CI流水线可运行lint和type check

### 2.3 技术要点

```bash
# 需要实现的核心文件
src/sdwan_desktop/
├── core/
│   ├── types/
│   │   ├── base.py          # BaseContract
│   │   ├── diagnosis.py     # DiagnosisResult, RootCause
│   │   ├── probe.py         # ProbeTarget, ProbeResult
│   │   └── context.py       # FlowContext, StepSnapshot
│   ├── errors/
│   │   ├── base.py          # BaseError
│   │   └── codes.py         # 错误码常量
│   └── constants/
│       └── severity.py      # Severity枚举
├── config/
│   ├── settings.py          # 配置类
│   └── loader.py            # YAML加载器
├── observability/
│   ├── logger.py            # 日志配置
│   └── tracer.py            # trace_id管理
└── interface/cli/
    └── main.py              # CLI入口
```

---

## 3. Sprint 2: 网络工具集

**周期**: 第2周 (40h)
**目标**: 实现全部网络探测工具，完成工具注册中心

### 3.1 任务清单

| ID | 任务 | 负责人 | 预估工时 | 依赖 | 状态 | 交付物 |
|---|----|-----|------|----|----|-----|
| 2.1 | ToolRegistry实现 | 后端 | 4h | 1.2 | ⬜ | registry/base.py |
| 2.2 | ToolDispatcher实现 | 后端 | 4h | 2.1 | ⬜ | dispatcher.py |
| 2.3 | tool_function装饰器 | 后端 | 2h | 2.1 | ⬜ | registry/decorator.py |
| 2.4 | PingTool实现 | 后端 | 4h | 2.2 | ⬜ | tools/network/ping.py |
| 2.5 | TraceRouteTool实现 | 后端 | 6h | 2.2 | ⬜ | tools/network/traceroute.py |
| 2.6 | TcpPortTool实现 | 后端 | 3h | 2.2 | ⬜ | tools/network/tcping.py |
| 2.7 | DnsTool实现 | 后端 | 4h | 2.2 | ⬜ | tools/network/dns.py |
| 2.8 | MtrTool实现 | 后端 | 4h | 2.4,2.5 | ⬜ | tools/network/mtr.py |
| 2.9 | WindowsSystemTool实现 | 后端 | 6h | 2.2 | ⬜ | tools/system/windows.py |
| 2.10 | SshAdapter实现 | 后端 | 4h | 2.2 | ⬜ | tools/remote/ssh.py |
| 2.11 | 工具层单元测试 | 后端 | 4h | 2.4-2.10 | ⬜ | test_tools/*.py |

### 3.2 验收标准

1. 所有工具通过ToolDispatcher调用
2. 每个工具包含超时控制
3. 工具返回统一的ToolResponse格式
4. WindowsSystemTool可正确采集网卡/路由/DNS/代理信息
5. SshAdapter可连接测试设备并执行命令
6. 工具层单元测试覆盖率 >70% (PATCH-001)

### 3.3 技术要点

```python
# 工具实现模板
@tool_function(
    name="ping",
    description="ICMP连通性测试",
    timeout=30,
    retry_count=2
)
class PingTool:
    def execute(self, request: ToolRequest, ctx: Context) -> ToolResponse:
        # 1. 参数校验
        # 2. 执行探测
        # 3. 构造ProbeResult
        # 4. 返回ToolResponse
        pass
```

---

## 4. Sprint 3: 一键体检
**周期**: 第3-4周 (80h)
**目标**: 实现完整的QuickCheck流程，包括采集、探测、规则分析和报告生成

### 4.1 任务清单
| ID | 任务 | 负责人 | 预估工时 | 依赖 | 状态 | 交付物 |
|---|---|---|---|---|---|---|
| **Week 3** | | | | | | |
| 3.1 | 配置采集器实现 | 后端 | 8h | 2.9 | ⬜ | collector/windows_collector.py |
| 3.2 | 探测目标配置 | 后端 | 4h | 1.6 | ⬜ | configs/quick_check.yaml |
| 3.3 | 连通性测试服务 | 后端 | 6h | 2.4,2.5,2.7 | ⬜ | services/connectivity.py |
| 3.4 | DNS分流检测服务 | 后端 | 6h | 2.7 | ⬜ | services/dns_split.py |
| 3.5 | 规则引擎框架 | 后端 | 8h | 1.2 | ⬜ | analyzer/rule_engine.py |
| 3.6 | 网关规则实现 | 后端 | 4h | 3.5 | ⬜ | analyzer/rules/gateway.py |
| **Week 4** | | | | | | |
| 3.7 | DNS规则实现 | 后端 | 4h | 3.5 | ⬜ | analyzer/rules/dns.py |
| 3.8 | 路由/代理/防火墙规则 | 后端 | 6h | 3.5 | ⬜ | analyzer/rules/system.py |
| 3.9 | 连通性规则实现 | 后端 | 4h | 3.5 | ⬜ | analyzer/rules/connectivity.py |
| 3.10 | QuickCheck Flow定义 | 后端 | 4h	3.1-3.9 | ⬜ | flow/definitions/quick_check.py |
| 3.11 | PipelineEngine实现 | 后端 | 8h | 1.4 | ⬜ | runtime/engine.py, executor.py |
| 3.12 | 基础HTML报告模板 | 全栈 | 8h | 3.10 | ⬜ | templates/quick_check.html |
| 3.13 | 报告生成服务 | 后端 | 4h | 3.12 | ⬜ | services/reporter/html_builder.py |
| 3.14 | CLI命令实现 | 后端 | 2h | 3.10,3.13 | ⬜ | cli/commands/quick_check.py |
| 3.15 | 流程集成测试 | 后端 | 4h | 3.14 | ⬜ | tests/flow/test_quick_check.py |

### 4.2 验收标准

1. 一键体检可采集全部Windows配置信息
2. 可正确测试网关/国内DNS/国际DNS/连通性目标
3. 至少实现15条诊断规则
4. 诊断结果包含置信度和证据引用
5. 生成的HTML报告包含元信息/摘要/结论/证据/建议
6. CLI命令 agentctl quick-check 可完整执行
7. 流程测试覆盖率 >80%

### 4.3 关键产出物

```yaml
# 需要实现的规则清单
规则ID:
  - ADAPTER-001: 网卡未连接
  - ADAPTER-002: 网卡速度异常
  - IP-001: APIPA地址
  - IP-002: IP地址冲突
  - GW-001: 网关不可达
  - GW-002: 网关延迟过高
  - GW-003: 网关丢包
  - DNS-001: DNS服务器无响应
  - DNS-002: DNS响应慢
  - ROUTE-001: 多条默认路由
  - PROXY-001: 系统代理已启用
  - PROXY-002: 代理不可达
  - FW-001: 防火墙阻止ICMP
  - INET-001: 国内网络不通
  - INET-002: 国际网络不通
  - INET-003: 国际链路丢包严重
  - SPLIT-001: DNS分流异常
```

---

## 5. Sprint 4: 深度诊断
**周期**: 第5-6周 (80h)
**目标**: 实现CPE联合诊断，包括SSH采集、配置解析、拓扑构建和根因分析

### 5.1 任务清单

| ID | 任务 | 负责人 | 预估工时 | 依赖 | 状态 | 交付物 |
|---|---|---|---|---|---|---|
| **Week 5** | | | | | | |
| 4.1 | CPE配置解析器基类 | 后端 | 4h | 1.2 | ⬜ | parser/vendor/init.py |
| 4.2 | Cisco SD-WAN解析器 | 后端 | 12h | 4.1 | ⬜ | parser/vendor/cisco_sdwan.py |
| 4.3 | 命令模板配置 | 后端 | 4h | 4.2 | ⬜ | configs/commands/cisco_sdwan.yaml |
| 4.4 | CPE采集服务 | 后端 | 8h | 2.10,4.3 | ⬜ | services/collector/cpe_collector.py |
| 4.5 | 配置一致性校验 | 后端 | 6h | 4.2,3.1 | ⬜ | services/validator/config_validator.py |
| 4.6 | 拓扑构建服务 | 后端 | 8h | 4.2,3.1 | ⬜ | services/analyzer/topology_builder.py |
| **Week 6** | | | | | | |
| 4.7 | Overlay状态分析 | 后端 | 6h | 4.6 | ⬜ | services/analyzer/overlay_analyzer.py |
| 4.8 | NAT类型识别 | 后端 | 4h | 4.6 | ⬜ | services/analyzer/nat_detector.py |
| 4.9 | 根因分析引擎 | 后端 | 8h | 4.5-4.8 | ⬜ | services/analyzer/root_cause.py |
| 4.10 | DeepDive Flow定义 | 后端 | 4h | 4.9 | ⬜ | flow/definitions/deep_dive.py |
| 4.11 | 专业HTML报告模板 | 全栈 | 8h | 4.6,4.9 | ⬜ | templates/deep_dive.html |
| 4.12 | 拓扑图渲染(Mermaid) | 全栈 | 4h | 4.11 | ⬜ | templates/components/topology.html |
| 4.13 | CLI命令实现 | 后端 | 2h | 4.10 | ⬜ | cli/commands/deep_dive.py |
| 4.14 | 深度诊断集成测试 | 后端 | 4h | 4.13 | ⬜ | tests/flow/test_deep_dive.py |

### 5.2 验收标准

1. 可成功连接Cisco SD-WAN设备并采集配置
2. 正确解析接口/路由/SD-WAN策略/隧道状态
3. 拓扑图正确展示PC-CPE-上联网关-Hub节点
4. 可识别单级/多级NAT场景
5. 根因分析至少覆盖5种SD-WAN典型故障
6. 报告包含配置对比表和拓扑图
7. CLI命令 agentctl deep-dive --cpe 192.168.1.1 可执行

### 5.3 关键产出物

```python
# 需要实现的根因规则
SD-WAN根因规则:
  - CPE-001: CPE不可达
  - CPE-002: SD-WAN隧道Down
  - CPE-003: 策略路由未生效
  - CPE-004: NAT规则不匹配
  - OVERLAY-001: BFD会话Down
  - OVERLAY-002: 隧道MTU问题
  - SPLIT-002: 分流策略与实际路径不符
```

### 5.4 业务不通根因（与 Sprint 4 并行迭代）

| ID | 任务 | 说明 | 状态 |
|----|------|------|------|
| 4.15 | 业务 RCA 证据模型与融合 | `business_rca.py` 契约、`BusinessRCAEngine`、`business-diagnose` 默认 PC 采集、DNS 对照、`deep-dive` 经 `RootCauseEngine` 统一入口；验收见 `tests/unit/services/diagnosis/test_business_rca_qa_matrix.py` | ✅ DONE |

---


## 6. Sprint 5: 业务监测

**周期**: 第7周 (40h)
**目标**: 实现URL访问Waterfall分析功能

### 6.1 任务清单

| ID | 任务 | 负责人 | 预估工时 | 依赖 | 状态 | 交付物 |
|---|---|---|---|---|---|---|
| 5.1 | Playwright集成 | 后端 | 6h | 1.1 | ⬜ | tools/web/har_capture.py |
| 5.2 | HAR解析服务 | 后端 | 6h | 5.1 | ⬜ | services/parser/har_parser.py |
| 5.3 | 性能指标提取 | 后端 | 4h | 5.2 | ⬜ | services/analyzer/perf_analyzer.py |
| 5.4 | 瓶颈分析规则 | 后端 | 4h | 5.3 | ⬜ | analyzer/rules/performance.py |
| 5.5 | Waterfall Flow定义 | 后端 | 4h | 5.1-5.4 | ⬜ | flow/definitions/waterfall.py |
| 5.6 | Waterfall HTML模板 | 全栈 | 8h | 5.5 | ⬜ | templates/waterfall.html |
| 5.7 | 时序图渲染(Chart.js) | 全栈 | 4h | 5.6 | ⬜ | templates/js/waterfall.js |
| 5.8 | CLI命令实现 | 后端 | 2h | 5.5 | ⬜ | cli/commands/waterfall.py |
| 5.9 | 集成测试 | 后端 | 2h | 5.8 | ⬜ | tests/flow/test_waterfall.py |

### 6.2 验收标准

1. 可成功录制指定URL的完整页面加载过程
2. HAR文件正确解析DNS/TCP/SSL/等待/下载各阶段耗时
3. Waterfall图表正确展示所有资源加载时序
4. 可识别最慢资源和阻塞渲染资源
5. 生成至少3条性能优化建议
6. CLI命令 agentctl waterfall --url https://example.com 可执行

### 6.3 关键产出物

```python
# 需要实现的性能规则
性能规则:
  - PERF-001: 页面加载时间过长(>3s)
  - PERF-002: DNS解析慢(>200ms)
  - PERF-003: TCP握手慢(>300ms)
  - PERF-004: SSL握手慢(>500ms)
  - PERF-005: TTFB过长(>600ms)
  - PERF-006: 资源下载慢(>2s)
  - PERF-007: 阻塞渲染资源
```

---

## 7. Sprint 6: GUI与报告

**周期**: 第8周 (40h)
**目标**: 实现PySide6桌面界面，完善所有HTML报告模板

### 7.1 任务清单

| ID | 任务 | 负责人 | 预估工时 | 依赖 | 状态 | 交付物 |
|---|---|---|---|---|---|---|
| 6.1 | 主窗口框架 | 全栈 | 6h | - | ⬜ | gui/main_window.py |
| 6.2 | 工具标签页 | 全栈 | 6h | 2.4-2.11 | ⬜ | gui/tabs/tools_tab.py |
| 6.3 | 一键体检标签页 | 全栈 | 6h | 3.10,3.13 | ⬜ | gui/tabs/quick_check_tab.py |
| 6.4 | 深度诊断标签页 | 全栈 | 6h | 4.10,4.11 | ⬜ | gui/tabs/deep_dive_tab.py |
| 6.5 | 业务监测标签页 | 全栈 | 4h | 5.5,5.6 | ⬜ | gui/tabs/waterfall_tab.py |
| 6.6 | 后台工作线程 | 全栈 | 4h | 6.2-6.5 | ⬜ | gui/workers/diagnosis_worker.py |
| 6.7 | 报告预览组件 | 全栈 | 4h | 6.3-6.5 | ⬜ | gui/widgets/report_viewer.py |
| 6.8 | 报告模板完善 | 全栈 | 4h | 3.12,4.11,5.6 | ⬜ | templates/*.html |

### 7.2 验收标准

1. GUI可正常启动，无崩溃
2. 所有工具可从界面独立调用
3. 一键体检/深度诊断/业务监测可完整执行
4. 报告可在界面内预览
5. 报告可保存到本地文件
6. 界面响应流畅，长任务不阻塞UI

### 7.3 界面布局

```text
┌─────────────────────────────────────────────────────────────┐
│ SD-WAN桌面诊断专家                                    - □ × │
├─────────────────────────────────────────────────────────────┤
│ [网络工具] [一键体检] [深度诊断] [业务监测]                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│                    (当前标签页内容)                           │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│ 状态: 就绪                              [进度条] [保存报告]   │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Sprint 7: 集成测试与优化

**周期**: 第9周 (40h)
**目标**: 端到端测试、性能优化、Bug修复

### 8.1 任务清单

| ID | 任务 | 负责人 | 预估工时 | 依赖 | 状态 | 交付物 |
|---|---|---|---|---|---|---|
| 7.1 | 端到端测试用例编写 | 全员 | 8h | 全部功能 | ⬜ | tests/e2e/*.py |
| 7.2 | 性能基准测试 | 后端 | 4h | 全部功能 | ⬜ | tests/benchmark/*.py |
| 7.3 | 内存泄漏检查 | 后端 | 4h | 6.1-6.8 | ⬜ | 内存分析报告 |
| 7.4 | 异常场景测试 | 后端 | 6h | 全部功能 | ⬜ | 测试用例 |
| 7.5 | GUI响应优化 | 全栈 | 4h | 6.1-6.8 | ⬜ | 优化后的界面 |
| 7.6 | 报告生成性能优化 | 全栈 | 4h | 3.13,4.11,5.6 | ⬜ | 优化后模板 |
| 7.7 | Bug修复 | 全员 | 10h | 7.1-7.6 | ⬜ | 修复记录 |

### 8.2 验收标准

1. 端到端测试全部通过
2. 一键体检执行时间 <30s
3. 深度诊断执行时间 <2min
4. 内存占用 <200MB (空闲时)
5. 所有已知Bug修复

### 8.3 性能指标

| 指标 | 目标值 | 测试方法 |
|---|---|---|
| 一键体检耗时 | <30s | 计时统计 |
| 深度诊断耗时 | <2min | 计时统计 |
| Waterfall耗时 | <45s | 计时统计 |
| GUI启动时间 | <3s | 计时统计 |
| 内存占用(空闲) | <200MB | 任务管理器 |
| CPU占用(空闲) | <5% | 任务管理器 |

---

## 9. Sprint 8: 发布准备

**周期**: 第10周 (40h)
**目标**: 打包发布、文档完善、最终验收

### 9.1 任务清单

| ID | 任务 | 负责人 | 预估工时 | 依赖 | 状态 | 交付物 |
|---|---|---|---|---|---|---|
| 8.1 | PyInstaller打包配置 | 全栈 | 6h | 全部功能 | ⬜ | build.spec |
| 8.2 | Windows安装包制作 | 全栈 | 6h | 8.1 | ⬜ | sdwan-diagnostic-setup.exe |
| 8.3 | 便携版打包 | 全栈 | 4h | 8.1 | ⬜ | sdwan-diagnostic-portable.zip |
| 8.4 | 用户手册编写 | 全员 | 8h | 全部功能 | ⬜ | docs/user_guide.md |
| 8.5 | 开发文档完善 | 后端 | 4h | 全部功能 | ⬜ | docs/developer_guide.md |
| 8.6 | API文档生成 | 后端 | 2h | 全部功能 | ⬜ | docs/api_reference.md |
| 8.7 | CHANGELOG编写 | 全员 | 2h | 全部功能 | ⬜ | CHANGELOG.md |
| 8.8 | 最终验收测试 | 全员 | 8h | 8.1-8.7 | ⬜ | 验收报告 |

### 9.2 验收标准

1. 安装包可在Windows 10/11正常安装
2. 便携版解压即可运行
3. 用户手册覆盖所有功能
4. 所有文档与代码同步
5. 通过最终验收测试

### 9.3 发布检查清单

| 检查项 | 状态 | 备注 |
| 版本号更新 (1.0.0) | ⬜ | pyproject.toml |
| CHANGELOG完成 | ⬜ |  |
| 所有测试通过 | ⬜ | CI绿色 |
| 安全扫描通过 | ⬜ | 无高危漏洞 |
| 安装包签名 | ⬜ | 代码签名证书 |
| 用户手册完成 | ⬜ | |
| 官网更新 | ⬜ | 下载链接 |
| 发布公告 | ⬜ | |

---

## 10. 附录: 任务依赖关系图

### 10.1 核心模块依赖

```text
                    ┌─────────────────┐
                    │   1.1 项目初始化 │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
      ┌───────────┐  ┌───────────┐  ┌───────────┐
      │1.2 数据契约│  │1.6 配置管理│  │1.9 Pre-commit│
      └─────┬─────┘  └─────┬─────┘  └─────────────┘
            │              │
    ┌───────┴───────┐      │
    ▼               ▼      ▼
┌───────┐     ┌───────────┐
│1.4 Context│   │2.1 ToolRegistry│
└───────┘     └───────┬───┘
                      │
              ┌───────┴───────┐
              ▼               ▼
      ┌───────────┐   ┌───────────┐
      │2.4-2.10   │   │3.11 Pipeline│
      │网络工具集  │   │Engine      │
      └─────┬─────┘   └─────┬─────┘
            │               │
            └───────┬───────┘
                    ▼
            ┌───────────────┐
            │ 3.10/4.10/5.5 │
            │   Flow定义     │
            └───────────────┘
```

### 10.2 功能模块依赖

```text
QuickCheck (Sprint 3)
    ├── WindowsSystemTool (Sprint 2)
    ├── PingTool/TraceTool/DnsTool (Sprint 2)
    ├── RuleEngine
    └── HtmlReporter

DeepDive (Sprint 4)
    ├── WindowsSystemTool (Sprint 2)
    ├── SshAdapter (Sprint 2)
    ├── ConfigParser (Sprint 4)
    ├── TopologyBuilder (Sprint 4)
    ├── RootCauseEngine (Sprint 4)
    └── HtmlReporter

Waterfall (Sprint 5)
    ├── HarCaptureTool (Sprint 5)
    ├── HarParser (Sprint 5)
    ├── PerfAnalyzer (Sprint 5)
    └── WaterfallReporter

GUI (Sprint 6)
    ├── 所有Tool (Sprint 2)
    ├── QuickCheck (Sprint 3)
    ├── DeepDive (Sprint 4)
    └── Waterfall (Sprint 5)
```

### 10.3 风险与应对
| 风险 | 概率 | 影响 | 应对措施 | 负责人 |
|---|---|---|---|---|
| Windows | WMI采集不稳定 | 中 | 高 | 预备PowerShell备选方案 | 后端 |
| CPE | SSH连接超时 | 中 | 中 | 增加重试和超时配置 | 后端 |
| Playwright首次启动慢 | 高 | 低 | 预下载Chromium | 全栈 |
| PyInstaller打包遗漏依赖 | 中 | 高 | 充分测试，使用spec文件 | 全栈 |
| 多厂商解析器扩展困难 | 低 | 中 | 先聚焦单厂商，预留接口 | 后端 |
