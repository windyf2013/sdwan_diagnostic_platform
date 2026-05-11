# 系统模式 (System Patterns)

## 分层架构

```text
Interface (CLI/GUI)
└── Orchestration (Flow Engine)
└── Service (业务逻辑)
└── Tool (工具抽象，通过 Dispatcher)
```

- **依赖方向**: 上层依赖下层，禁止反向。Core 层零依赖。

## 核心设计模式

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| 数据契约基类 | `core/types/base.py` | 所有数据对象继承 `BaseContract`，内置 id/trace_id/timestamp |
| 工具注册表 | `tools/registry` | 工具单例注册，元数据驱动，`ToolDispatcher` 唯一调用入口 |
| 纯函数规则 | `services/analyzer/rules` | 诊断规则用 `@pure_function` 标记，无副作用，接收上下文返回 `Optional[RootCause]` |
| 流程编排 | `flow/definitions` | 用 DAG 声明步骤依赖，`FlowRuntime` 按拓扑执行，记录 step snapshot |
| 配置分层加载 | `config/loader` | YAML 配置支持环境覆盖、用户覆盖，阈值从配置读取 |

## 流程执行模式 (Sprint 3 实施)

一键体检步骤依赖：

```text
step-1 (系统采集)
├── step-2 (网关测试) ──┐
└── step-3 (DNS测试) ───┼── step-4 (互联网连通性)
│
└── step-5 (DNS分流)
│
▼
step-6 (规则分析)
│
▼
step-7 (结论生成)
│
▼
step-8 (报告生成)
```

- 并行组: [step-2, step-3] 可并发
- 失败策略: `continue_on_error` 允许部分失败继续
- 快照: 每个步骤记录 `StepSnapshot` 用于回放

## 数据流契约

- 工具输入: `ToolRequest` → 输出: `ToolResponse` (裸 dict，Sprint 3 转为强类型)
- 服务层消费强类型对象 (`SystemInfoSnapshot`, `ConnectivityTestResult`)
- 规则引擎聚合为 `QuickCheckContext` → 输出 `List[RootCause]`
- 报告输入: `DiagnosisResult` → 模板渲染 → HTML

## 异常与容错

- **错误分级**: VAL_* (校验) → TOOL_* (工具) → FLOW_* (流程) → TIME_* (超时) → SYS_* (系统)
- **采集容错**: 单项采集失败记录日志并继续，返回部分数据
- **规则容错**: 规则函数自身捕获异常，失败不影响其他规则
- **超时控制**: 每个步骤独立超时，支持重试策略

## 关键技术选型

| 领域 | 选择 | 原因 |
|------|------|------|
| 类型系统 | dataclass + pydantic | 内部对象用 dataclass (性能)，边界校验用 pydantic |
| 异步 | asyncio | 并发探测，Semaphore 控制并发度 |
| CLI | click | 子命令组织，与 agentctl 契合 |
| 配置 | YAML + 自定义 Loader | 支持多环境、多层级覆盖 |
| 报告 | Jinja2 + HTML | 模板化生成，支持响应式布局 |
| 测试 | pytest + pytest-asyncio | 异步测试、覆盖率 |
| 质量 | mypy + ruff | 类型/风格一致性 |

## 报告结构约定 (Sprint 3 实施)

用户报告必须包含：
1. 元信息 (报告 ID, trace_id, 时间, 规则版本)
2. 执行摘要 (严重程度、一句话总结、置信度)
3. 检测结果表格 (按严重程度排序)
4. 根因分析 (标题、描述、置信度、证据引用)
5. 诊断建议 (优先级排序)
6. 证据附录 (可折叠原始证据)
