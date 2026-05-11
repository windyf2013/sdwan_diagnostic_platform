# AI Agent Python 工程标准体系（Spec）

**文档编号**: AAPS-001  
**适用范围**: AI Agent 工程（multi-agent / tool system / workflow system）、Python 后端工程、可编排任务系统、工具调用系统  
**规范等级**: Mandatory（强制执行）  
**生效方式**: 新增模块必须遵循，存量模块按迭代计划迁移

---

## 0. Profile 分层治理模型（Core / SDWAN）

为兼顾通用工程治理与领域增强，本规范采用双 Profile 生效机制。

### 0.1 Profile 定义

1. **Core Profile（通用基线）**
   - 适用于所有 Python 模块（默认强制）。
   - 目标：保证工程一致性、可维护性、安全性、可发布性。

2. **SDWAN Profile（领域增强）**
   - 仅适用于 SD-WAN 诊断域模块（按触发条件或目录归属启用）。
   - 目标：保证诊断流程可回放、证据可追溯、结论可解释、生产网络安全可控。

### 0.2 冲突与优先级

- 在 SDWAN 作用域内：`SDWAN Profile > Core Profile`。
- 在非 SDWAN 作用域内：仅 Core Profile 强制生效。
- 若条款冲突且未覆盖，按“安全优先、正确性次之、性能再次、迁移成本最后”裁决。

### 0.3 条款分级标签（执行语义）

- `MUST`：强制；违反即阻断合并/发布。
- `SHOULD`：建议；允许豁免，但需登记原因与失效日期。
- `CONDITIONAL`：条件强制；满足触发条件即升级为 MUST。

### 0.4 Conditional 触发条件

任一条件满足时，`Flow / Tool Dispatcher / SDWAN 增强条款` 自动升级为 MUST：

- 涉及 2 个及以上外部工具或探针。
- 诊断路径存在 >= 3 个步骤的编排链路。
- 需要 retry/replay 或异步任务队列。
- 对外提供诊断 API 或结构化诊断报告。
- 涉及生产网络访问或设备探测。

### 0.5 目录映射示例（Profile Scope）

| 目录 | 默认 Profile | 备注 |
| --- | --- | --- |
| `src/sdwan_analyzer/core/` | Core | 通用契约、类型、基础设施封装 |
| `src/sdwan_analyzer/service/` | Core | 业务逻辑（若编排复杂可触发 Conditional） |
| `src/sdwan_analyzer/probe/` | SDWAN | 探针实现、协议探测、采样策略 |
| `src/sdwan_analyzer/diagnosis/` | SDWAN | 根因分析、证据融合、诊断判定 |
| `src/sdwan_analyzer/reporting/` | SDWAN | 诊断输出 schema 与报告生成 |

## 1. 工程总体架构标准（Architecture Standard）

### 1.1 架构分层

工程必须采用分层架构，且所有模块必须归属单一层级：

1. **Interface Layer（CLI / API / Agent Entry）**
   - 职责：接收外部输入、参数校验、组装标准化 `AgentInput`、返回 `AgentOutput`。
   - 禁止：承载业务规则、直接调用工具实现细节。

2. **Orchestration Layer（Flow Engine / Task Scheduler）**
   - 职责：基于 Flow 定义调度步骤、状态迁移、分支决策、重试与回放控制。
   - 禁止：直接实现业务算法与底层 IO。

3. **Service Layer（Business Logic）**
   - 职责：实现领域业务能力，消费上下文与工具抽象结果，输出结构化业务结果。
   - 禁止：流程编排硬编码、基础设施细节耦合。

4. **Tool Layer（External Tools）**
   - 职责：封装网络工具、API 工具、自动化工具等外部能力，暴露统一 `Tool Schema`。
   - 禁止：依赖业务层实现、包含业务策略判断。

5. **Core Layer（Data Contract / Types）**
   - 职责：定义系统数据契约、类型、枚举、协议、错误码。
   - 禁止：依赖任何上层实现或运行时组件。

6. **Infra Layer（Logging / Config / Storage）**
   - 职责：日志、配置、存储、序列化、追踪、队列、缓存等基础设施能力。
   - 禁止：承载业务决策与流程分支策略。

### 1.2 架构原则

以下原则为强制规则：

1. **数据驱动，不是函数驱动**
   - 流程推进必须基于 `FlowState` 与 `Context` 的状态变化。
   - 禁止通过散乱函数调用链隐式推进流程。

2. **流程可编排（not hard-coded）**
   - Flow 定义必须声明为配置化结构（DAG / Pipeline / State Machine）。
   - 禁止在业务函数中硬编码下一步骤。

3. **所有调用必须显式**
   - 调用链必须可追踪：调用方、被调方、输入、输出、trace_id。
   - 禁止隐式 side effect 与隐藏调用。

4. **工具必须 registry 化**
   - 所有工具必须注册到统一 `Tool Registry`，由 `Tool Dispatcher` 调度。
   - 禁止直接实例化工具并跨模块私调。

5. **状态必须集中管理（Context Object）**
   - 所有跨步骤共享状态必须进入 `Context`。
   - 禁止模块级全局变量承载运行时状态。

### 1.3 模块边界规则

#### 1.3.1 依赖规则（Dependency Rule）

- Interface Layer -> Orchestration Layer / Core Layer
- Orchestration Layer -> Service Layer / Tool Layer / Core Layer / Infra Layer
- Service Layer -> Tool Layer（仅通过 Dispatcher 抽象）/ Core Layer / Infra Layer
- Tool Layer -> Core Layer / Infra Layer
- Infra Layer -> Core Layer
- Core Layer -> 无依赖（仅标准库与类型系统）

#### 1.3.2 跨层调用约束

- Interface Layer 禁止直接调用 Tool Layer。
- Service Layer 禁止绕过 Orchestration 进行流程编排。
- Tool Layer 禁止反向依赖 Service Layer 与 Orchestration Layer。
- Core Layer 禁止依赖任何上层模块。
- 任一层禁止通过循环依赖构建“隐式中间层”。

### 1.4 目录结构标准

标准工程目录必须至少包含以下结构：

```text
project_root/
│
├── spec/  
│   ├─ README.md                          # 系统规范层（唯一事实源，不参与运行）
│   │
│   ├─00_core
│   │      ├── data_contract.md
│   │      ├── error_model.md
│   │      ├── runtime_environment.md
│   │      ├── spec_invariants.md
│   │      ├── spec_registry.md
│   │      ├── state_context.md
│   │
│   ├─10_architecture
│   │      ├── concurrency_model.md
│   │      ├── dependency_model.md
│   │      ├── execution_governance.md
│   │      ├── execution_model.md
│   │      ├── execution_safety_boundary.md
│   │      ├── layering_model.md
│   │
│   ├─20_domain
│   │  ├─analysis
│   │  │   ├── correlation_model.md
│   │  │   ├── diagnosis_model.md
│   │  │
│   │  ├─config
│   │  │   ├── config_schema.md
│   │  │
│   │  ├─probe
│   │  │   ├── probe_dns.md
│   │  │   ├── probe_http.md
│   │  │   ├── probe_icmp.md
│   │  │   ├── probe_ssh_telnet.md
│   │  │   ├── probe_tcp.md
│   │  │
│   │  ├─reporting
│   │  │   ├── report_schema.md
│   │  │   ├── severity_model.md
│   │  │
│   │  ├─system
│   │  │   ├── system_probe.md
│   │  │
│   │  ├─topology
│   │  │   ├── edge_model.md
│   │  │   ├── graph_model.md
│   │  │   ├── node_model.md
│   │  │
│   │  └─traffic
│   │      ├── flow_model.md
│   │      ├── session_model.md
│   │
│   ├─30_rfc
│   │  ├─analysis
│   │  │   ├── rfc_causality_engine.md
│   │  │   ├── rfc_correlation_engine.md
│   │  │   ├── rfc_diagnosis_engine.md
│   │  │
│   │  ├─config
│   │  │   ├── rfc_config_parser.md
│   │  │
│   │  ├─probe
│   │  │   ├── rfc_probe_dns.md
│   │  │   ├── rfc_probe_http.md
│   │  │   ├── rfc_probe_icmp.md
│   │  │   ├── rfc_probe_ssh_telnet.md
│   │  │   ├── rfc_probe_tcp.md
│   │  │
│   │  ├─reporting
│   │  │   ├── rfc_report_generator.md
│   │  │   ├── rfc_severity_engine.md
│   │  │
│   │  ├─system
│   │  │   ├── rfc_system_probe.md
│   │  │   ├── rfc_version_control.md
│   │  │
│   │  ├─topology
│   │  │   ├── rfc_topology_graph.md
│   │  │
│   │  └─traffic
│   │      ├── rfc_traffic_flow.md
│   │      ├── rfc_traffic_session.md
│   │
│   ├─40_atomic
│   │  │   ├── retry_policy.md
│   │  │   ├── sampling_policy.md
│   │  │   ├── timeout_policy.md
│   │  │
│   │  └─tooling
│   │      ├── dns_adapter.md
│   │      ├── http_adapter.md
│   │      ├── ping_adapter.md
│   │      ├── tcp_adapter.md
│   │
│   ├─50_execution
│   │      ├── determinism_engine.md
│   │      ├── external_interface.md
│   │      ├── pipeline_engine.md
│   │      ├── plugin_lifecycle.md
│   │      ├── resource_manager.md
│   │      ├── runtime.md
│   │
│   ├─55_observability
│   │      ├── logging_standard.md
│   │      ├── replay_engine.md
│   │      ├── trace_model.md
│   │
│   ├─60_examples
│   │      ├── flow_examples.md
│   │      ├── probe_examples.md
│   │      ├── report_examples.md
│   │      ├── topology_examples.md
│   │
│   └─70_validation
│          ├── registry_validator.md
│          ├── rule_checker.md
│          ├── schema_validator.md
│          ├── simulation_framework.md
│          ├── spec_drift_control.md
│
├── src/                          #  可执行代码层（唯一 runtime）
│   └── agent_system/             #  Python package root
│
│       ├── __init__.py
│
│       ├── core/                 # 核心基础层（无业务）
│       │   ├── types/            # dataclass / pydantic models
│       │   ├── context/          # Context 生命周期
│       │   ├── errors/           # error definitions
│       │   ├── constants/
│       │
│       ├── runtime/              #  执行引擎（flow executor）
│       │   ├── engine.py         # flow runtime core
│       │   ├── executor.py       # step executor
│       │   ├── scheduler.py      # task scheduling
│       │   ├── dispatcher.py     # execution routing
│       │
│       ├── flow/                 #  流程定义（不是执行）
│       │   ├── definitions/
│       │   ├── pipelines/
│       │   ├── dags/
│       │
│       ├── services/             #  业务逻辑层（纯逻辑）
│       │   ├── analyzer/
│       │   ├── decision/
│       │   ├── processor/
│       │
│       ├── tools/                #  工具层（必须 registry 管理）
│       │   ├── registry/
│       │   ├── implementations/
│       │   ├── adapters/
│       │   ├── builtin/
│       │
│       ├── interface/            #  外部入口层
│       │   ├── cli/
│       │   ├── api/
│       │   ├── agent_entry.py
│       │
│       ├── observability/        #  trace / log / replay
│       │   ├── tracer.py
│       │   ├── logger.py
│       │   ├── recorder.py
│       │   ├── replay.py
│       │
│       ├── config/               #  配置系统
│       │   ├── settings.py
│       │   ├── env.py
│       │
│       ├── runtime_validator/    #  spec enforcement layer
│       │   ├── base.py
│       │   ├── data_validator.py
│       │   ├── flow_validator.py
│       │   ├── tool_validator.py
│       │   ├── function_validator.py
│       │
│       ├── bootstrap/            #  启动系统
│       │   ├── app.py
│       │   ├── loader.py
│
├── tests/                        #  测试层
│   ├── unit/
│   ├── flow/
│   ├── tools/
│   ├── integration/
│
├── scripts/                      #  工具脚本
│   ├── run_flow.py
│   ├── debug_trace.py
│   ├── build.py
│
├── configs/                      #  环境配置（非 runtime）
│   ├── dev.yaml
│   ├── prod.yaml
│   ├── test.yaml
│
├── docs/                         #  文档（非 spec）
│   ├── architecture.md
│   ├── design_decisions.md
│
├── pyproject.toml               #  Python packaging
├── README.md
├── Dockerfile                   # optional
├── .gitignore
├── Makefile                     # optional build automation
```

---

## 2. 编码规范标准（Coding Spec）

### 2.1 数据结构规范（强制）

系统必须定义并统一使用以下数据模型：

- `AgentInput`
- `AgentOutput`
- `Context`
- `ToolRequest`
- `ToolResponse`
- `FlowState`

#### 2.1.1 结构化约束

- 必须使用 Python type hints，且仅允许 `pydantic`、`dataclass`、`TypedDict` 三类结构化模型。
- 禁止裸 `dict` 在跨层接口中传递。
- 所有结构必须可 JSON 序列化。
- 所有结构必须包含 `trace_id`、`id`、`timestamp` 字段。

#### 2.1.2 模型选型与使用范围（强制）

##### A. pydantic 使用范围

必须用于以下场景：

- Interface Layer 的入参与出参校验（CLI / API / Agent Entry）。
- Tool Dispatcher 的请求参数校验与响应反序列化。
- 外部输入（HTTP、消息队列、配置文件、环境变量）进入系统边界时。

规则：

- 必须开启严格模式（或等效严格校验策略），禁止隐式类型转换。
- 必须定义字段约束（长度、范围、枚举、格式）与默认值策略。
- 必须在模型层完成业务前置校验，失败统一抛出 `ValidationError`。

禁止项：

- 禁止将 pydantic 模型直接下沉为领域计算核心对象（核心计算优先 `dataclass`）。
- 禁止在纯计算密集路径频繁创建 pydantic 对象导致性能退化。

##### B. dataclass 使用范围

必须用于以下场景：

- Service Layer / Orchestration Layer / Core Layer 的内部领域对象。
- FlowState、Context、StepNode 等运行时状态对象。
- 纯函数输入输出对象（不涉及外部输入校验时）。

规则：

- 必须显式类型标注，建议 `@dataclass(slots=True)`。
- 必须保持不可变语义优先（可行时使用 `frozen=True`）。
- 必须提供可序列化转换方法（如 `to_json_dict` / mapper）。

禁止项：

- 禁止直接接收未校验外部原始数据构造 dataclass。
- 禁止在 dataclass 中写入隐式 IO 逻辑。

##### C. TypedDict 使用范围

仅允许用于以下场景：

- 工具层与第三方 SDK 的临时兼容层（typed mapping 过渡结构）。
- JSON 字段形状声明但无需运行时实例行为的轻量场景。
- 历史模块迁移阶段的过渡契约（需有迁移截止计划）。

规则：

- 必须声明 `total` 策略（`total=True/False`）并显式可选字段。
- 必须在进入关键流程前转换为 `pydantic` 或 `dataclass`。

禁止项：

- 禁止将 TypedDict 作为跨层长期公共契约。
- 禁止将 TypedDict 用作 Context、FlowState、ToolRequest、ToolResponse 的最终模型。

##### D. 统一选型优先级（决策顺序）

1. 涉及外部输入校验与边界防御：**优先 pydantic**
2. 涉及内部领域建模与计算：**优先 dataclass**
3. 仅需静态字典形状声明且为短期兼容：**允许 TypedDict**

若出现争议，按“边界安全优先、运行性能次之、迁移成本最后”原则裁决。

#### 2.1.3 推荐契约基类

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class BaseContract:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=utc_now_iso)

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
        }
```

### 2.2 函数规范（强制）

#### 2.2.1 函数契约总则

- 每个函数必须声明：`Input Contract`、`Output Contract`、`Error Contract`、`Side-Effect Contract`。
- 输入必须是结构化对象，不得使用 `*args/**kwargs` 承载业务数据。
- 输出必须是结构化对象，不得返回多态裸值（如 `str | dict | None` 混用）。
- 禁止隐式全局状态读写。
- 必须实现 IO 与业务逻辑分离。
- 所有公开函数必须在 docstring 或同级契约注释中声明前置条件与后置条件。

#### 2.2.2 统一函数签名模板（强制）

公开函数必须遵循统一签名风格：

```python
def fn_name(input_data: InputModel, ctx: Context) -> OutputModel:
    ...
```

约束：

- `input_data` 必须为单一主输入对象（结构化）。
- `ctx` 必须显式传入，不得从全局读取运行时上下文。
- 返回值必须为单一结构化对象；错误通过标准异常体系抛出。
- `trace_id` 必须通过 `ctx` 贯穿，不允许函数内部生成新主链路 `trace_id`。

异步函数模板：

```python
async def fn_name(input_data: InputModel, ctx: Context) -> OutputModel:
    ...
```

#### 2.2.3 函数分类标准（可组合约束）

1. **pure function**
   - 无副作用，仅依赖输入参数。
   - 允许：数据转换、规则计算、策略评估。
   - 禁止：日志写入、网络请求、文件读写、随机源与系统时钟直读。

2. **service function**
   - 处理领域逻辑，调用工具抽象结果。
   - 不直接处理 CLI 参数与底层网络细节。
   - 必须通过契约组合 pure function 与 tool function。

3. **tool function**
   - 仅封装外部系统交互（HTTP / shell / browser / file）。
   - 输入输出必须满足 `ToolRequest/ToolResponse` 契约。
   - 禁止承载业务决策与流程路由。

4. **orchestrator function**
   - 仅负责步骤编排、状态推进、失败恢复。
   - 禁止包含具体业务规则与外部调用细节实现。
   - 必须输出可重放的步骤执行记录。

#### 2.2.4 可组合规则（Composition Rules）

- 组合单元必须是“契约稳定函数”（输入输出契约版本可追踪）。
- 允许组合方向：`orchestrator -> service -> (pure + tool)`。
- 禁止组合方向：`tool -> service`、`tool -> orchestrator`、`pure -> tool`（隐式 IO）。
- 单函数最大职责：只完成一个可命名业务意图（Single Intent Rule）。
- 函数组合必须保持幂等边界可声明（尤其在 retry/replay 场景）。

#### 2.2.5 可验证规则（Verifiability Rules）

每个函数必须可被以下维度验证：

1. **契约验证**
   - 输入非法时必须触发 `ValidationError` 或其子类。
   - 输出必须满足声明类型与字段完整性。

2. **行为验证**
   - pure function 必须提供确定性测试（同输入同输出）。
   - service function 必须提供业务规则测试（含边界条件）。
   - tool function 必须提供超时、重试、错误映射测试。
   - orchestrator function 必须提供分支与回放一致性测试。

3. **副作用验证**
   - 每个含 IO 函数必须声明副作用类别（network/file/process/db）。
   - 测试中必须可替换为 mock/fake，不得强依赖生产外部系统。

#### 2.2.6 前置条件 / 后置条件规范

- 前置条件（Preconditions）必须覆盖：必填字段、取值范围、依赖状态。
- 后置条件（Postconditions）必须覆盖：返回结构完整性、状态变化、错误语义。
- 不满足前置条件必须快速失败（fail-fast），不得降级为静默默认值。
- 后置条件失败必须抛出 `FlowError` 或 `SYS_*` 系列错误并保留上下文。

#### 2.2.7 禁止模式（函数层）

- 禁止函数内同时包含“复杂业务决策 + 多外部 IO 调用”。
- 禁止在函数内部动态修改全局配置对象。
- 禁止在无契约声明的情况下透传第三方 SDK 原始对象到上层。
- 禁止返回 `Any` 作为公开函数返回类型。

#### 2.2.8 函数契约审查矩阵（CR/CI 可执行）

| 函数类型 | 必须满足的契约项 | 最低测试要求 | CI 阻断条件 |
|---|---|---|---|
| `pure function` | 明确 `Input/Output Contract`；无副作用声明为 `none`；不得依赖全局状态 | 参数边界测试 + 确定性测试（同输入同输出） | 出现 IO 调用、随机/时间直读、全局可变状态读写即阻断 |
| `service function` | 明确业务前置/后置条件；错误映射到标准错误体系；显式依赖声明 | 规则分支测试 + 异常路径测试 + 契约完整性测试 | 返回裸值、错误类型不合规、未声明副作用即阻断 |
| `tool function` | 必须使用 `ToolRequest/ToolResponse`；声明超时/重试/幂等策略；禁止业务决策 | 成功/失败/超时/重试测试 + schema 校验测试 | 绕过 Dispatcher、无 schema、错误未映射 `ToolError` 即阻断 |
| `orchestrator function` | 声明步骤输入输出契约；记录 trace 与 step 状态；可回放 | 分支覆盖测试 + retry/replay 一致性测试 | 无 step 级日志、无 replay 数据、跨层直接调用即阻断 |

审查执行规则：

1. Code Review 必须逐行核对上述矩阵，任何一项未满足即 `Request Changes`。
2. CI 必须提供自动化检查：类型检查、契约检查、测试覆盖、禁用模式扫描。
3. 合并门禁必须包含函数契约检查任务；任务失败时禁止合并。
4. 对遗留代码允许临时豁免，但必须附带迁移 issue 与截止版本号。

建议最小自动化实现：

- `mypy/pyright`：函数签名与类型契约检查。
- `ruff/flake8 + 自定义规则`：禁止模式扫描（全局状态、print、Any 返回）。
- `pytest`：按函数类型分组执行（`@pytest.mark.pure/service/tool/orchestrator`）。
- 覆盖率门槛：`pure >= 95%`，`service >= 90%`，`tool >= 85%`，`orchestrator >= 90%`。

### 2.3 流程规范（Flow Spec）

#### 2.3.1 Flow 形态

Flow 必须采用以下三类之一：

- DAG
- Pipeline
- State Machine

不得使用隐式 if/else 链替代流程定义。

标准 Flow 模型:
Flow = {
    nodes: [],
    edges: [],
    context: {},
    state: {}
}

#### 2.3.2 StepNode 标准结构

每个 Step 必须包含：

- `input`
- `output`
- `status`
- `retry_policy`
- `error_handler`
- `timestamp`
- `trace_id`

推荐结构：

```python
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(slots=True)
class RetryPolicy:
    max_attempts: int
    backoff_seconds: float


@dataclass(slots=True)
class StepNode:
    id: str
    trace_id: str
    input: object
    output: Optional[object]
    status: str
    retry_policy: RetryPolicy
    error_handler: Callable[[Exception], object]
```

#### 2.3.3 流程能力要求

Flow 引擎必须支持：

- replay（按 `trace_id` 与 step snapshot 回放）
- retry（按 step 级策略重试）
- branching（基于状态与条件分支）

### 2.4 工具系统规范（Tool System）

必须包含以下组件：

1. **Tool Registry**
   - 统一注册工具元数据、版本、schema、权限标签。

2. **Tool Dispatcher**
   - 唯一工具调用入口；负责参数校验、鉴权、执行、超时、重试、日志。

3. **Tool Schema**
   - 定义工具输入输出契约、错误码、幂等策略、超时策略。

#### 2.4.1 工具约束

- 工具必须独立封装，单工具单职责。
- 输入输出必须结构化（`ToolRequest` / `ToolResponse`）。
- 工具禁止直接耦合业务逻辑。
- 所有工具调用必须通过 `Tool Dispatcher`。

### 2.5 错误体系规范（Error Model）

必须定义统一错误模型与分层错误类型：

- `BaseError`
- `ValidationError`
- `ToolError`
- `FlowError`
- `TimeoutError`

每个错误必须包含：

- `error_code`
- `message`
- `context`
- `trace_id`

推荐基类：

```python
class BaseError(Exception):
    def __init__(self, error_code: str, message: str, context: dict, trace_id: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.context = context
        self.trace_id = trace_id
```

错误编码规则：

- `VAL_*`: 输入与契约校验错误
- `TOOL_*`: 外部工具调用错误
- `FLOW_*`: 编排与状态迁移错误
- `TIME_*`: 超时错误
- `SYS_*`: 未分类系统错误

### 2.6 可观测性规范（Observability）

必须实现以下能力：

1. **trace_id 全链路**
   - 所有日志、错误、事件、快照必须携带 `trace_id`。

2. **step-level logging**
   - 每一步记录 start/end/status/duration/retry_count。

3. **input/output snapshot**
   - step 输入输出快照可持久化（脱敏后）。

4. **replay capability**
   - 支持基于 trace 的流程重放与诊断。

日志规范要求：

- 必须使用结构化日志（JSON Line 或同等格式）。
- 禁止 `print` 替代 logging。
- 日志字段最小集合：`timestamp`, `level`, `trace_id`, `step_id`, `event`, `payload_hash`。

### 2.7 Python 命名规范（Naming Convention）

命名规则为强制项，必须满足 PEP 8 与本规范约束：

1. **目录命名（package / directory）**
   - 必须使用全小写 `snake_case`。
   - 禁止使用连字符（`-`）、空格、拼音缩写歧义词。
   - 目录名必须表达领域语义而非技术细节（如 `topology`、`traffic`、`reporting`）。

2. **文件命名（module file）**
   - 必须使用全小写 `snake_case.py`。
   - 禁止使用 `util.py`、`common.py`、`misc.py` 等无语义名称（可作为迁移期例外，需逐步拆分）。
   - 测试文件必须使用 `test_*.py` 或 `*_test.py`（项目内选择一种并保持一致）。

3. **类与异常命名（class / exception）**
   - 类名必须使用 `PascalCase`。
   - 抽象基类建议使用语义后缀（如 `BaseRepository`、`AbstractProbe`）。
   - 自定义异常必须以 `Error` 结尾（如 `ValidationError`、`ToolTimeoutError`）。

4. **函数与方法命名（function / method）**
   - 必须使用 `snake_case`，并使用动词或动宾短语（如 `parse_config`、`build_flow_graph`）。
   - 布尔返回函数建议使用 `is_` / `has_` / `can_` 前缀。
   - 工厂函数建议使用 `create_` / `build_` 前缀。

5. **变量、常量与内部符号命名（variable / constant / internal）**
   - 普通变量必须使用 `snake_case`。
   - 常量必须使用全大写 `UPPER_SNAKE_CASE`，集中定义在模块顶部或专用常量模块。
   - 私有实现符号必须使用单前缀下划线（如 `_load_cache`、`_session`）。
   - 禁止使用单字符变量名（循环计数器 `i/j/k` 与数学上下文除外）。

6. **类型变量与泛型命名（typing）**
   - `TypeVar` 必须使用 `PascalCase` 单词（如 `TResult`、`TContext`）。
   - 协议、TypedDict、数据模型命名应与领域对象一致，禁止与基础类型重名（如 `List`、`Dict`）。

推荐示例：

```python
MAX_RETRY_ATTEMPTS = 3


class FlowExecutionError(Exception):
    pass


def build_step_context(trace_id: str, step_id: str) -> dict:
    is_retryable = True
    return {"trace_id": trace_id, "step_id": step_id, "is_retryable": is_retryable}
```

### 2.8 导入导出与模块边界规范（Import/Export Contract）

本节为强制项，用于约束类/函数的导入路径、对外暴露边界与可执行治理机制。

#### 2.8.1 导入规则（Import Rules）

1. **导入路径规则**
   - 必须优先使用绝对导入（基于项目根 package），禁止跨层相对导入穿透目录边界。
   - 同一模块内导入顺序必须统一：标准库 -> 第三方 -> 本地模块。
   - 禁止 `from x import *`。

2. **跨层导入规则**
   - 必须遵守 `1.3.1` 依赖方向；任何反向导入视为阻断缺陷。
   - Service Layer 访问 Tool Layer 必须经由 `Tool Dispatcher` 抽象，禁止直连实现模块。
   - Core Layer 禁止导入任何上层模块（Interface/Orchestration/Service/Tool/Infra）。

3. **循环依赖规则**
   - 禁止模块级循环依赖与延迟导入规避架构约束。
   - 为打破循环依赖而引入的本地函数内 `import` 仅可作为临时迁移措施，必须在迭代内消除并登记技术债。

#### 2.8.2 导出规则（Export Rules）

1. **公共 API 边界**
   - package 级公共 API 必须在 `__init__.py` 显式导出，并通过 `__all__` 声明对外符号集合。
   - 未纳入 `__all__` 的符号视为内部实现，不得被跨模块依赖。
   - 内部实现类/函数必须使用 `_` 前缀或放置在 `internal`/`_private` 语义目录中。

2. **重导出规则**
   - 允许在包入口进行受控 re-export（用于稳定 API）；禁止多级链式重导出导致来源不透明。
   - 对外导出的类必须保持来源可追踪（文档或注释标明 canonical module）。

3. **兼容性规则**
   - 删除或重命名已导出的公共类/函数属于破坏性变更，必须遵循 SemVer MAJOR 升级。
   - 公共导出面变更必须更新 README/API 文档与变更记录。

#### 2.8.3 强约束机制（Enforcement）

CI 必须阻断以下检查失败：

1. **静态导入质量检查**
   - `ruff`：导入排序、未使用导入、通配符导入等规则。
   - `isort`：导入分组与顺序一致性。

2. **架构依赖检查**
   - 必须使用 `import-linter`（或同等工具）声明层级 contract，并校验禁止导入关系。
   - 必须校验 Core Layer 不被上层反向污染，Service 不直连 Tool 实现细节。

3. **公共 API 面检查**
   - 对关键 package 必须存在 `__all__` 一致性测试（导出清单与文档/契约一致）。
   - 必须有 smoke test 验证公共导出路径可稳定导入（例如 `from package import PublicClass`）。

### 2.9 安全与合规规范（Security & Compliance Spec）

本节为强制项，覆盖身份认证、授权、密钥治理、数据保护与审计要求。

#### 2.9.1 身份认证与授权

- 所有外部入口（CLI/API/Agent Entry）必须进行身份认证与请求来源校验。
- 工具调用权限必须采用最小权限原则（least privilege），禁止默认全量权限。
- 必须定义角色模型（RBAC）或属性模型（ABAC），并可审计“谁在何时调用了什么工具”。
- 高风险操作（删除、写入外部系统、执行命令）必须配置显式授权策略与可撤销开关。

#### 2.9.2 密钥与凭据管理

- 密钥、Token、证书、数据库凭据必须存放在密钥管理系统或环境密文注入链路中。
- 禁止明文密钥写入代码库、日志、异常堆栈、测试快照。
- 必须具备密钥轮换机制，支持定期轮换与紧急吊销。
- 必须区分 dev/stage/prod 凭据，禁止跨环境复用高权限凭据。

#### 2.9.3 数据保护与隐私

- 必须对敏感字段（凭据、PII、业务敏感字段）执行分级分类与脱敏策略。
- 日志、trace、快照中必须默认脱敏，需白名单机制才可明文输出。
- 传输链路必须使用 TLS；敏感数据落盘必须加密或存储于受控介质。
- 必须定义数据保留期与删除策略，满足合规最小保留原则。

#### 2.9.4 安全审计与供应链

- 必须启用依赖漏洞扫描与许可证合规扫描（阻断高危漏洞进入发布）。
- 构建产物必须可追踪（commit SHA、依赖摘要、签名信息）。
- 必须保留审计日志：认证结果、授权决策、敏感操作、配置变更。

### 2.10 运行时可靠性规范（Reliability / SLO Spec）

#### 2.10.1 SLI/SLO 强制定义

- 每个核心能力必须定义 SLI（成功率、延迟、错误率、吞吐）。
- 每个核心能力必须定义 SLO（例如 P95 延迟、月可用性目标）与错误预算。
- 未定义 SLO 的新服务/新流程禁止进入生产发布。

#### 2.10.2 失败处理与降级

- 必须定义超时、重试、熔断、限流、隔离舱壁（bulkhead）策略。
- 重试必须有上限与退避策略，禁止无限重试放大故障。
- 必须提供降级路径（只读模式、缓存回退、部分功能关闭）。
- 必须定义“不可恢复故障”的 fail-fast 与告警升级策略。

#### 2.10.3 容量与性能基线

- 必须建立容量模型（QPS、并发数、任务队列深度、资源上限）。
- 必须在发布前完成基线压测，并记录关键阈值。
- 当性能退化超过阈值（如 P95 增长 > 20%）时，发布应自动阻断。

### 2.11 状态一致性与恢复规范（State Consistency & Recovery）

#### 2.11.1 状态模型与幂等

- 所有可重试步骤必须定义幂等键（idempotency key）与去重语义。
- 状态迁移必须有显式状态机定义，禁止隐式“多写即成功”。
- 必须定义并发冲突处理策略（乐观锁、版本号、最后写入策略等）。

#### 2.11.2 持久化与回放

- step snapshot 必须定义保留周期、压缩策略与访问权限。
- replay 必须可复现关键输入条件（配置版本、工具版本、上下文版本）。
- 必须定义“可回放边界”和“不可回放步骤”（例如外部副作用步骤）的补偿策略。

#### 2.11.3 灾备与恢复目标

- 必须定义 RTO/RPO 目标，并在系统级文档中登记。
- 必须定期执行恢复演练（数据恢复、流程恢复、服务切换），并保留报告。
- 未通过恢复演练验证的关键变更不得进入生产。

### 2.12 契约演进与兼容规范（API Evolution Spec）

#### 2.12.1 变更分级

- 契约变更必须标注为 `breaking` / `non-breaking` / `internal`。
- `breaking` 变更必须触发 MAJOR 升级并提供迁移指南。
- `non-breaking` 变更必须保持向后兼容并补充默认值与兼容路径。

#### 2.12.2 弃用与迁移

- 公共接口弃用必须提供 `deprecation window`（建议至少一个 MINOR 周期）。
- 必须在文档、CHANGELOG、运行日志中标注弃用通知。
- 必须提供迁移示例与自动化检查（静态扫描旧 API 调用）。

#### 2.12.3 契约测试与发布门禁

- 必须有契约测试覆盖新旧版本输入输出兼容性。
- 必须在 CI 中执行向后兼容测试矩阵（N 与 N-1 至少一档）。
- 契约文档未更新或兼容测试失败时，发布必须阻断。

### 2.13 注释与调试可观测规范（Comments & Debug Observability）

本节为强制项，覆盖代码注释、文档字符串、调试日志、调试快照与报告隔离边界。

#### 2.13.1 注释与文档字符串（Docstring/Comment）

- 所有公开模块、公开类、公开函数必须提供 docstring，说明职责、输入输出契约、异常语义。
- 复杂逻辑（分支判定、状态迁移、容错策略）必须有“为什么”注释，禁止仅重复代码字面含义。
- 注释必须与实现同步变更；发现过期注释视为缺陷，需在同次变更中修复。
- 禁止保留无效注释块（废弃方案、临时调试说明）进入主分支。

#### 2.13.2 调试日志分级与开关（Debug Logging Control）

- 调试信息必须通过 logging 体系输出，禁止 `print`、`pprint`、临时 stdout/stderr 输出。
- 必须区分日志级别：`DEBUG` 仅用于开发/排障，生产默认不输出高噪声调试详情。
- 必须提供可审计的 debug 开关（配置项或环境变量），并记录启停时间与操作者。
- 调试日志必须继承 `trace_id` 与 `step_id`，确保可回溯。

#### 2.13.3 调试快照与敏感信息保护（Debug Snapshot Hygiene）

- 调试快照必须默认脱敏；凭据、Token、密钥、PII 字段禁止明文落盘。
- 调试快照必须定义保留周期与访问权限，禁止无限期保留。
- 为排障临时开启的扩展日志/快照必须在故障处置后自动或手动回收。

#### 2.13.4 诊断输出与调试信息隔离（Report Boundary）

- 对外报告禁止包含内部调试字段（如原始堆栈、内部模块路径、临时特征位）。
- 报告层仅允许暴露经审查的证据摘要，不得直接透传原始 debug payload。
- 若需导出深度排障包，必须走受控通道（权限校验、脱敏、审计留痕）。

#### 2.13.5 强约束机制（Enforcement）

- CI 必须执行注释/docstring 覆盖检查（公开 API 缺失文档即阻断）。
- CI 必须执行禁止模式扫描（`print`、`pprint`、未受控 debug 开关、明文敏感日志）。
- 报告 schema 校验必须阻断未授权 debug 字段外泄。

---

## 3. 打包与发布标准（Build & Packaging）

### 3.1 项目打包结构标准

项目必须采用 `src layout`：

```text
src/
pyproject.toml
README.md
tests/
configs/
```

#### 3.1.1 pyproject.toml 强制项

- 必须声明构建后端（建议 `hatchling` 或 `setuptools`）。
- 必须声明项目元数据（name/version/requires-python/dependencies）。
- 必须声明 console scripts 入口。
- 必须包含质量工具配置（lint/type/test）。
- 代码命名规范见 `2.7 Python 命名规范（Naming Convention）`。

### 3.2 依赖管理规范

- 必须区分 production 与 dev dependencies。
- 必须维护 lock file（如 `uv.lock` / `poetry.lock` / `requirements.lock`）。
- 版本策略：
  - 运行时核心依赖：`~=x.y` 或精确 pin（关键基础库允许精确 pin）。
  - 构建工具链：精确 pin 或最小版本 + CI 校验。
- 禁止未声明依赖被隐式安装与使用。

### 3.3 CLI / EntryPoint 规范

- CLI 必须提供统一入口（如 `agentctl`）。
- 命令必须通过 command registry 注册。
- 参数必须有 schema（类型、默认值、必填、枚举、校验规则）。
- CLI 只做输入解析与响应渲染，不得承载业务逻辑。
- **用户可见行为、交互边界、人机报告形态**：以 **第 4 章** 为完整规范；本章仅保留打包入口层面的最低要求。

### 3.4 发布标准（Release Spec）

#### 3.4.1 版本规范

- 必须采用 SemVer：`MAJOR.MINOR.PATCH`。
- 破坏性变更提升 MAJOR。
- 向后兼容功能提升 MINOR。
- 缺陷修复提升 PATCH。

#### 3.4.2 构建流水线

标准流水线阶段：

1. lint
2. type check
3. unit/flow/tool tests
4. build package
5. artifact scan
6. publish

#### 3.4.3 打包策略

- 默认产物：`wheel`。
- 可选产物：`onefile`（PyInstaller）或 `docker image`（部署场景要求时）。
- 发布产物必须含版本号、构建时间、commit SHA、依赖摘要。

#### 3.4.4 Release Checklist

- 版本号已更新
- CHANGELOG 已更新
- 所有 CI 通过
- 回归测试通过
- 关键 Flow 回放验证通过
- 产物签名与校验完成
- 回滚方案可用

### 3.5 测试与验证标准

必须覆盖：

1. **unit test**
   - 纯函数与服务函数行为验证。

2. **flow test**
   - 编排路径、分支、重试、回放一致性验证。

3. **tool test**
   - 工具 schema 校验、超时、失败重试、幂等行为验证。

强制要求：

- CI-ready structure（可在无人工介入下执行）。
- deterministic test execution（固定随机种子、可控时间、外部依赖 mock）。
- 禁止依赖真实生产环境网络资源作为默认测试前提。

### 3.6 质量门禁基线（Quality Gates）

发布流水线必须包含以下阻断门禁：

1. **代码质量门禁**
   - lint/type check 全量通过。
   - 圈复杂度、重复率、函数长度必须在阈值内（阈值由项目配置声明）。

2. **测试质量门禁**
   - 单元测试、流程测试、工具测试必须全量通过。
   - 覆盖率不得低于基线阈值（建议 line >= 80%，核心模块 branch >= 70%）。

3. **性能与可靠性门禁**
   - 必须通过基线性能测试（关键路径延迟、吞吐、资源占用）。
   - SLO 退化超过阈值（如 P95 增幅 > 20%）必须阻断发布。

4. **安全与供应链门禁**
   - 依赖漏洞扫描不得存在未豁免高危漏洞。
   - 制品签名、依赖摘要、SBOM（或同等级清单）必须生成并可追踪。

---

## 4. 用户交互与呈现标准（User Interaction & Presentation）

本章规定**面向人类用户与自动化系统**的交互边界、命令行形态与用户可见报告形态。与 `2.13` 报告边界、`5.7` 诊断输出契约配合使用：本章偏「产品与 UX 契约」，彼处偏「数据与安全边界」。

### 4.1 用户交互限制（User Interaction Constraints）

#### 4.1.1 默认非交互（MUST）

- 默认执行路径必须**可在无 TTY、无人工输入**下完成（CI、cron、Agent 批量任务）。
- 凡需用户确认、多步问答或菜单选择的流程，必须**显式**通过子命令或标志开启（如 `--interactive` / `confirm` 子命令），且须在帮助文档中说明阻塞条件。
- 禁止在默认路径上使用 `input()` 式隐式暂停；禁止「未说明即等待 stdin」导致自动化挂起。

#### 4.1.2 敏感信息与凭据（MUST）

- 禁止将密钥、密码、Token、私钥材料通过** argv 明文**传入（进程列表与 shell 历史可泄露）。
- 凭据输入优先序：`安全环境变量` / `受权限约束的配置文件` / `交互式安全回显关闭输入`（仅当已启用交互模式）；禁止写入日志与报告正文。
- 对用户展示的连接串、URL 必须脱敏（掩码 host 后缀或凭证段）。

#### 4.1.3 危险操作与生产影响（MUST）

- 凡可能改变设备配置、影响转发/会话或触发写操作的行为，必须：**显式目标** + **危险等级说明** + **二次确认或 `--yes` 类非默认标志**（与 `5.6` 一致）。
- **dry-run / preview**：SHOULD 提供只读预览或计划输出，且默认不执行写操作。

#### 4.1.4 输出信道与用户可见性（MUST）

- **结果与摘要**：默认写入 **stdout**；**错误、诊断提示、弃用警告**：写入 **stderr**，除非 `--json` 等机器模式另有统一约定。
- 日志（`logging`）与用户可见「命令输出」分离：用户报告不经由 debug 日志通道拼接；参见 `2.13.2`、`2.13.4`。
- 终端编码：文档与 CLI 约定 **UTF-8**；非 UTF-8 环境应降级为可打印 ASCII 提示，而非静默损坏。

#### 4.1.5 自动化与可解析性（MUST）

- 同一命令必须同时支持**人类可读**与**机器可读**（至少一种稳定 `--format json` 或专用 `--json`），且机器输出必须为稳定 schema（版本化见 `4.3`）。
- 机器可读输出必须写入 stdout，且**仅包含约定字段**；进度条、提示语不得污染 JSON 行（或约定分离至 stderr）。

#### 4.1.6 体验下限（SHOULD）

- 长耗时任务应提供确定性进度或可查询的 `trace_id` / 任务 id，便于异步排障。
- 破坏性变更的 CLI：在弃用期内同时支持旧标志并给出 stderr 警告（与 `2.12` 一致）。

#### 4.1.7 文件与交换格式编码（Encoding & Text Exchange）

本节约束**文本形态**的源码、配置、CLI 管道与机器交换产物；二进制制品（证书、pcap 等）不在此列，但须在 schema 中标注 `content_type`。

**仓库与编辑器（MUST）**

- Python 源码、规范文档（Markdown）、以及纳入版本控制的 **JSON / YAML / TOML / INI 类配置**：必须使用 **UTF-8** 编码；**禁止带 UTF-8 BOM**（避免双解释与 diff 噪声），除非外部工具强制要求且须在文档中声明例外。
- 版本库内文本换行：SHOULD 统一为 **LF**（`eol=lf`）；Windows 检出策略由项目 `.gitattributes` 明确，避免混用 CRLF/LF 导致校验失败。

**运行时读写（MUST）**

- 读入用户或外部系统提供的文本文件时：默认按 **UTF-8** 解码；遇非法字节须**失败可诊断**（指出路径与偏移），禁止静默替换为 `?` 导致证据损坏。
- 写出生成物（报告 JSON、导出 Markdown、日志轮转文本）：默认 **UTF-8**，与 `4.1.4` 终端约定一致。

**结构化交换（MUST）**

- **JSON**：UTF-8 文本；字段与字符串值中的非 ASCII 须合法转义或由标准库/序列化器生成；禁止依赖「非标准 JSON」扩展作为默认路径。
- **YAML**：UTF-8；禁止在默认配置路径依赖仅 YAML 1.1 的模糊类型陷阱而不加显式 tag/schema。
- CLI **管道与重定向**：将 stdout/stderr 视为 UTF-8 字节流；若平台编码非 UTF-8，须在文档说明限制或提供 `--encoding`（SHOULD）。

**用户报告导出（MUST / SHOULD）**

- **Markdown / HTML / JSON 报告文件**：MUST 为 UTF-8（无 BOM）；HTML 须声明 `<meta charset="utf-8">` 或等价 HTTP 头。
- **CSV**（若提供）：MUST 在帮助或 schema 中声明编码；面向 Excel 互操作时允许 **UTF-8 BOM** 作为可选导出模式并单独命名（避免与默认无 BOM 混用）。

#### 4.1.8 与 Git / 版本控制对齐（Git & VCS Baseline）

本节保证工程规则**可被 Git 管理、可 diff、可 CI 检出复现**，与「业务 Flow 回放」正交：前者管**仓库与协作**，后者管**运行时诊断链路**。

**仓库元文件（MUST）**

- 仓库根目录必须提供 **`.gitignore`**，排除：虚拟环境、构建产物、缓存、本地 IDE/工具目录、含密钥或环境覆写的路径（如 `.env`、未脱敏快照目录）；与 `1.4` 目录示例中的 `.gitignore` 一致并随工程演进更新。
- 必须提供 **`.gitattributes`**（或与组织统一模板等价），落实 **4.1.7** 中文本换行与「文本/二进制」判定，避免跨 OS 检出导致哈希与 golden file 不一致。

**可提交内容与体积（MUST / SHOULD）**

- **禁止**将密钥、生产凭据、未脱敏客户数据、可反推内网的完整拓扑/配置快照纳入默认跟踪路径（与 `4.1.2`、`6` 一致）；若确需测试夹具，须使用合成数据或脱敏子目录并文档说明。
- 大文件（抓包、大型数据集、预训练权重等）：**禁止**无策略地直接进普通 Git 对象库；SHOULD 使用 **Git LFS**、制品库或外部只读引用，并在 README/spec 中说明获取方式。

**版本与变更可追溯（MUST）**

- 发布与契约变更须维护 **CHANGELOG** 与 **SemVer**（见 `3.4`）；Git **tag** 与 `pyproject` 版本应对齐或可脚本校验，避免「仓库标签与安装版本」漂移。

**协作与门禁（SHOULD）**

- 主分支保护、PR 评审、CI 通过后再合并：与 `7` 治理条款一致；具体分支模型（Git Flow / trunk-based）由项目选定，但须与「禁止未满足强制条款即合并」不冲突。

**pre-commit 与本地 Git 钩子（SHOULD；启用后升级为 MUST）**

- **SHOULD**：采用 **[pre-commit](https://pre-commit.com/)** 框架，在仓库根**纳入版本控制** **`.pre-commit-config.yaml`**；各 hook 的 `rev` **固定到明确 tag/commit**，禁止「浮动 latest」导致不可复现。
- **MUST**（**CONDITIONAL**：仓库已存在 `.pre-commit-config.yaml` 或团队约定使用 pre-commit 时）：  
  - **CI** 必须在合并前执行**与配置等价**的检查（例如 `pre-commit run --all-files`，或对每条 hook 调用等价命令），与 `3.6` 质量门禁**同一基线**（同一套 lint/format 规则与主要版本），避免「本地过、CI 挂」。  
  - 默认合入路径**禁止**依赖 `--no-verify` / `SKIP` 跳过；确需跳过须在 PR **书面说明原因、风险与补救期限**（应急 hotfix 流程可单独约定）。
- **SHOULD**：钩子集合**至少**覆盖以下类别（具体 repo 可增减，但须在 PR 模板或 `CONTRIBUTING` 中说明）：  
  - 文本与换行：`trailing-whitespace`、`end-of-file-fixer`、与 **4.1.7** 一致的行尾与编码假设；  
  - 结构化文件：`check-yaml`、`check-json` / `check-toml`（或等效校验）；  
  - **密钥与敏感信息**：`gitleaks`、`detect-secrets` 或组织批准的等价扫描，与 `4.1.2`、`6` 一致；  
  - **Python 质量**：与 `3.6` 对齐的 `ruff` / `black` / `mypy` 等（避免本地与 CI 使用不同配置路径）。  
- **SHOULD**：在 `README` 或 **`CONTRIBUTING.md`** 中写明本地安装：`pre-commit install`；若使用 **`commit-msg`** 类钩子，写明 `pre-commit install --hook-type commit-msg`。
- **提交信息（Conventional Commits）**：**SHOULD** 采用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)（`feat:`、`fix:`、`chore:` 等）以便与 **CHANGELOG**、发版说明自动化衔接；若项目**声明启用**，则 **`commit-msg` 校验**（pre-commit 或 CI）为 **MUST**。
- **等价方案**：允许 **Lefthook**、**Husky**（多见于 Monorepo 前端）、或 `core.hooksPath` 下的**受版本控制脚本**，但必须满足：**配置与脚本入仓、文档化安装步骤、CI 可复现同一规则**；不得仅依赖个人机器上的未文档化钩子。

### 4.2 命令行设计规范（CLI Design Standard）

#### 4.2.1 结构与发现性（MUST）

- 采用**统一顶层入口** + **子命令**分层：`entry <noun> <verb>` 或 `entry <group> <command>`，同一项目内风格一致。
- 子命令必须在 `--help` 中分组列出；每个子命令必须有 **one-line 描述** + **示例**（可置于 epilog）。
- 必须实现 `--version`（或顶层 `version` 子命令），输出与 `pyproject` / 包元数据一致。

#### 4.2.2 参数与配置（MUST）

- **长选项**为主（`--output`），**短选项**为高频操作保留（`-o`）；含义冲突时禁止复用同一短字母。
- 参数必须有类型、默认值、必填性、枚举与范围校验；校验失败信息必须指向**用户可修正的字段名**与示例。
- 配置优先级必须在文档中写明并保持一致，建议：**CLI 参数 > 环境变量 > 项目/用户配置文件 > 默认值**。

#### 4.2.3 帮助与文档字符串（MUST）

- `--help` 文本必须说明：子命令用途、必填参数、危险标志、与 **4.1** 相关的交互假设（是否默认非交互）。
- 示例须可复制粘贴；涉及路径与主机名使用占位符（`<device>`），避免文档中的真实资产名。

#### 4.2.4 退出码（MUST）

- `0`：成功（含业务上「已完成且无致命错误」的约定成功语义）。
- 非 `0`：失败；必须文档化分类（如 `1` 一般错误、`2` 用法/校验错误、`3` 远程/工具失败、`4` 被用户取消），且**稳定**，不因日志级别变化而改变。
- 禁止用退出码传递复杂状态；复杂结果用结构化输出或 `AgentOutput`。

#### 4.2.5 输出形态（MUST）

- 提供**默认人类可读**视图（表格或分段文本），与 **`--format json|yaml|table`**（或项目选定集合）之一致 schema。
- 表格列宽与截断策略须避免泄露过长敏感字段；宽输出可提供 `--no-truncate` 类标志并默认安全截断。

#### 4.2.6 与实现分层对齐（MUST）

- CLI 层仅负责：解析、校验、装配 `AgentInput`、渲染、退出码映射；**禁止**在 `click`/`argparse` 回调中写业务分支与 IO 探针。
- 与 `1.1` Interface Layer 职责一致。

### 4.3 用户报告设计规范（User-Facing Report Design Standard）

本节约束**交付给终端用户或客户**的诊断/分析报告（含HTML页面、PDF、Markdown 导出及 CLI 摘要），与内部 engineering 调试包区分。

#### 4.3.1 受众与语气（MUST）

- 必须区分**操作者摘要**（结论、影响、建议动作）与**证据附录**（数据引用、时间范围）；禁止将内部模块名、堆栈、原始 probe blob 作为唯一叙述主体。
- 用语：陈述事实与建议，避免未定义缩写；首次出现的领域缩写须展开或附术语表。

#### 4.3.2 结构与必备章节（MUST）

用户可见报告**至少**包含：

1. **元信息**：报告类型、生成时间（带时区）、分析对象/范围、`trace_id` / `incident_id`（若存在）、工具与规则/schema 版本。
2. **执行摘要**：1 段话说明问题性质与当前判定状态（进行中/已结论）。
3. **结论**：分级结论列表，每条含**严重程度**（与 `5.7` / `spec/20_domain/reporting` 一致）、**简短理由**。
4. **证据**：可审计引用（probe 类型、采样时间、关键指标摘要），指向可追溯存储而非粘贴机密全文。
5. **建议动作**：可执行、可验证的步骤；影响生产的前置条件单独列出。
6. **局限与置信度**：已知缺口、降级路径（与 `5.5` 对齐）、置信度或需人工复核的明确提示。

#### 4.3.3 严重级别与一致性（MUST）

- 严重程度枚举与颜色/图标（若有）必须在全 CLI、Web、导出格式中**同源定义**，禁止同一语义多套名称。
- 禁止仅依赖颜色传达关键信息（色盲可访问性）；须配合文字标签。

#### 4.3.4 格式与稳定性（MUST / SHOULD）

- **MUST**：机器交换格式（JSON）字段名 **stable**，遵循 schema 版本策略（`2.12`）；破坏性重命名走 MAJOR；文本编码与换行约定遵循 **4.1.7**。
- **SHOULD**：人类可读默认 Markdown 或 HTML 模板化生成，样式与章节顺序受版本控制。
- PDF/打印导出：SHOULD 保留目录与页眉中的 `trace_id` 与版本，便于归档审计。

#### 4.3.5 安全与合规展示（MUST）

- 遵守 `2.13.3`、`2.13.4`：报告默认脱敏；扩展详情需授权与审计。
- 禁止在「用户报告」通道嵌入仅供内网的 URL 或未鉴权下载链接。

#### 4.3.6 版本与再现（SHOULD）

- 报告生成器应声明 **template / schema 版本**；同一输入在相同版本下应可重现（与时间戳、动态外部状态除外，须声明）。

---

## 5. SDWAN 增强规范（SDWAN Profile）

本章在 `0.x` 触发条件命中或模块归属 SDWAN 作用域时强制生效。

### 5.1 领域对象与契约（MUST）

- 必须定义并版本化以下核心对象：`Node`、`Edge`、`ProbeTarget`、`FlowSession`、`Incident`、`DiagnosisResult`。
- 领域对象必须具备稳定主键与时间语义（`collected_at`、`observed_at`、`trace_id`）。
- 诊断结论对象必须包含置信度、证据引用、规则/模型版本号。

### 5.2 诊断流程与编排（MUST）

- 诊断链路必须声明标准步骤：目标发现 -> 探针执行 -> 证据标准化 -> 关联分析 -> 结论生成。
- 每个步骤必须声明超时、重试、幂等与失败补偿策略。
- 必须支持按 `trace_id` 的链路回放，且回放输出可与原执行对比。

### 5.3 证据链与可解释性（MUST）

- 所有诊断结论必须可追溯到原始证据（probe 原始结果、时间戳、数据来源）。
- 禁止输出无法解释来源的“黑箱结论”作为最终报告。
- 报告必须包含：结论、证据摘要、置信度、建议动作、风险等级。

### 5.4 误报漏报治理（SHOULD）

- 应定义误报/漏报统计口径与复盘周期。
- 应建立阈值分级与冲突证据决策规则（高置信覆盖低置信或进入人工复核）。
- 对高影响误判，应提供快速回滚到上一规则版本的能力。

### 5.5 设备兼容与降级（CONDITIONAL -> MUST）

- 必须维护设备能力矩阵（厂商、协议版本、可执行探针集合）。
- 当探针不可用时，必须执行受控降级并记录“结论置信度下降原因”。
- 禁止因单一探针失败直接输出确定性根因结论。

### 5.6 生产网络安全边界（MUST）

- 默认只读探测；危险操作必须显式开关 + 二次确认。
- 必须实现探测频率限制、并发上限、目标白名单/黑名单机制。
- 任何可能影响生产流量的操作必须可审计、可撤销、可追踪。

### 5.7 诊断输出契约（MUST）

- 必须提供机器可读输出（JSON schema）与人类可读输出（报告模板）。
- 机器输出至少包含：`trace_id`、`incident_id`、`severity`、`root_causes`、`evidence_refs`、`recommendations`。
- 输出契约变更必须遵循 `2.12` 兼容性策略与契约测试门禁。
- 用户可见章节结构、CLI 行为与交互边界须同时满足 **第 4 章**。

---

## 6. 强制约束（Hard Rules）

以下条款为一票否决项：

- ❌ 禁止 dict 无结构传参
- ❌ 禁止函数混合 IO + business logic
- ❌ 禁止隐式全局状态
- ❌ 禁止工具直接调用业务逻辑
- ❌ 禁止流程 hard-code
- ❌ 禁止无 trace execution
- ❌ 禁止 print 替代 logging

补充禁止项：

- ❌ 禁止绕过 `Tool Dispatcher` 直接调用工具实现
- ❌ 禁止跨层循环依赖
- ❌ 禁止无 schema 的 CLI 参数进入业务层
- ❌ 禁止未版本化的发布产物进入制品库
- ❌ 禁止 `from module import *` 与未声明边界的公共导出
- ❌ 禁止跨层反向导入与通过函数内 `import` 长期规避依赖约束
- ❌ 禁止密钥/凭据明文进入代码、日志、快照与测试样本
- ❌ 禁止未定义 SLO/RTO/RPO 的关键流程进入生产发布
- ❌ 禁止缺失兼容性测试或迁移说明的破坏性契约变更发布
- ❌ 禁止未通过安全扫描与制品签名校验的构建产物发布
- ❌ 禁止公开 API 缺失 docstring 或存在与实现不一致的过期注释
- ❌ 禁止将内部 debug 字段、原始堆栈或敏感 payload 直接输出到对外报告
- ❌ 禁止在默认 CLI 路径上依赖交互式 stdin 或未经说明的阻塞提示
- ❌ 禁止通过 argv 传递密钥、密码、Token 等敏感凭据
- ❌ 禁止无文档化语义与稳定性的 CLI 退出码
- ❌ 禁止用户报告缺少结论/证据/建议/元信息（`trace_id` 或等价关联）中的任一必备块
- ❌ 禁止在已约定 pre-commit 的仓库中，仅以本地钩子代替 CI 对同一规则的强制校验（关键规则必须在 CI 可重复执行）

---

## 7. 执行与治理

- 本规范作为 AI Agent Python 工程唯一基线标准。
- Core Profile 为默认强制基线，SDWAN Profile 按作用域与触发条件升级生效。
- 代码评审必须将本规范作为阻断性检查项。
- CI 必须具备自动化规则校验能力（类型、结构、流程、日志、测试、CLI 契约与用户报告 schema）。
- 若启用 **pre-commit**（见 **4.1.8**），CI 必须复现其核心钩子或与之为**子集/等价超集**关系，禁止仅以「开发者本机已安装」为合入门禁。
- 未满足强制条款的变更不得合并。
