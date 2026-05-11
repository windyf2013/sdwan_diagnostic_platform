# Tech Context

**版本**: v0.2.0  
**更新**: 2026-04-24  
**阶段**: Sprint 2 ✅ / Sprint 3 📋  

---

## 1. 当前阶段

- **Sprint 1 ✅**  
  项目骨架、数据契约、错误体系、日志、配置、CLI、CI  

- **Sprint 2 ✅**  
  7 个工具全部实现，测试：91 passed / 12 skipped  

- **Sprint 3 📋**  
  采集器 → 连通性探测 → 规则引擎 → 流程编排 → HTML 报告  

---

## 2. 项目结构

```
src/sdwan_desktop/
├── core/types/
│   ├── base.py
│   ├── diagnosis.py
│   ├── probe.py
│   └── context.py
├── core/errors/
├── tools/
│   ├── registry/
│   ├── dispatcher.py
│   └── implementations/
│       ├── network/
│       ├── system/
│       └── remote/
├── runtime/
├── config/loader.py
├── observability/
├── interface/cli/
├── services/              # Sprint 3
├── flow/definitions/      # Sprint 3
└── reporting/             # Sprint 3
```

---

## 3. 核心运行时模型

### 工具调度

```python
from sdwan_desktop.tools.dispatcher import ToolDispatcher

dispatcher = ToolDispatcher()
result = await dispatcher.dispatch(
    "WindowsSystemTool",
    params={"command": "get_adapters"}
)
```

返回示例：

```python
{"adapters": [{"name": "...", "mac_address": "..."}]}
```

---

### 数据流

- 输入：`ToolRequest`
- 输出：`ToolResponse`
- 当前：业务层直接使用 `dict`
- 计划：Sprint 3 引入强类型 DataClass

---

### 已实现工具

| 工具 | 用途 | 覆盖率 |
|------|------|--------|
| PingTool | ping 解析 | 85% |
| TraceRouteTool | tracert 解析 | 93% |
| TcpPortTool | 端口检测 | 84% |
| DnsTool | DNS 解析 | 48% |
| MtrTool | 路由追踪 | — |
| WindowsSystemTool | 系统采集 | 28% |
| SshAdapter | SSH 执行 | 40% |

---

## 4. 强制约束

- 数据结构必须使用 `@dataclass(slots=True)`
- 函数签名统一：`fn(input, ctx) -> output`
- 禁止使用 `*args/**kwargs`
- 纯函数必须使用 `@pure_function`
- 工具调用必须通过 `ToolDispatcher`
- 禁止在工具中写业务逻辑
- 使用 `logging`，禁止 `print`
- 必须包含 `trace_id`
- 错误采用分层错误码
- 配置禁止硬编码
- 使用绝对导入 + `__all__`

---

## 5. 关键接口

### ToolDispatcher

```python
result = await ToolDispatcher().dispatch(
    "WindowsSystemTool",
    params={"command": "get_adapters"}
)
```

### FlowContext

```python
FlowContext(
    logger=...,
    trace_id=...,
    data={},
    steps=[]
)
```

### pure_function

```python
@pure_function
def my_rule(ctx):
    ...
```

### 配置加载

```python
cfg = ConfigLoader().get("quick_check")
```

---

## 6. 数据契约

- **BaseContract**: id, trace_id, timestamp
- **DiagnosisResult**
- **RootCause**
- **Severity**
- **ProbeResult**
- **StepSnapshot**

---

## 7. 技术债务

| 问题 | 计划 |
|------|------|
| 测试覆盖率低 | 提升至 ≥70% |
| 返回 dict | 改为强类型 |
| Flow 未验证 | Sprint 3 实现 |
| 报告缺失 | Sprint 3 完成 |
| 缺少集成测试 | Sprint 3 添加 |

---

## 8. Sprint 3 规划

| 模块 | 文件 | 状态 |
|------|------|------|
| 采集器 | collector | 📋 |
| 连通性 | connectivity | 📋 |
| DNS 分流 | dns_split | 📋 |
| 规则引擎 | rule_engine | 📋 |
| Rules | rules/* | 📋 |
| Flow | quick_check | 📋 |
| 报告 | html_builder | 📋 |
| CLI | commands | 📋 |

---

## 9. 环境

- Python: 3.13.2
- 包管理: uv / pip
- 工具: mypy / ruff / pytest
- CI: GitHub Actions
- OS: Windows 10/11 x64
