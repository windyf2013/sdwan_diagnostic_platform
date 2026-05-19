# Tech Context

**版本**: v0.2.3  
**更新**: 2026-05-12（deep-dive 拓扑与PC节点展示修复）  
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

---

## 10. CPE 深度诊断凭证（configs，2026-05）

| 文件 | 用途 |
|------|------|
| `configs/cpe_credentials.yaml` | `devices.<管理IP>.password` / `testnode_password`；按 IP 与当前连接目标匹配；勿提交版本库。 |
| `configs/cpe_view_credentials.yaml` | `views.testnode` / `diagnose` / `su` / `enable`；不按设备，作全环境默认二次口令；勿提交。 |

- 加载模块：`services/collector/cpe_credentials_loader.py`、`cpe_view_credentials_loader.py`。
- 运行时合并：`CpeCollectorConfig` + `CpeCollector._password_for_view`（详见代码与 `activeContext.md`）。
- **未实现**：应用内凭据列表、新增/删除设备、编辑写回 YAML（见 `progress.md` 已记录需求 REQ-CRED-001）。

---

## 11. CPE Telnet（telnetlib3）与 Raisecom MSG5200 诊断入口

- **终端协商**：`CpeCollector._connect_telnet` 强制 `TelnetClient`（避免 TTY 下 `TelnetTerminalClient` 用本机 NAWS 尺寸）、`term="vt100"`、`cols=80`、`rows=24`、`send_environ=("TERM","LANG")`，并处理 banner 已含登录提示时的空等。
- **EOF / 误匹配**：对端 EOF 时空读立即 `ConnectionError`；进入诊断 shell 时**不得**用含 `host#` 的通用提示符结束首轮读取，否则会误判已进入 bash、在 CLI 下发 shell 命令导致 EOF。
- **5200A（PV A.00）与 5200B（PV B.00）**：在 **enable（`<name>#`**；未配置 hostname 时 `name` 为 host）下，5200A 使用 **`diagnose`**；部分 4.3x 在 enable 无 `diagnose` 时先 **test-node** 再 `diagnose`。5200B 使用 **`su`**，口令见 `views.su`。提示符可能是 **`bash-N.N#`** 或 busybox **`#`**；`_diagnostic_shell_prompt_seen` 与 `_execute_telnet_plain` 共用匹配集。模板命令统一 **`diagnose:...`**，由 `_enter_diagnose_view` 按 `_active_device_type` 分支。
- **`testnode:`**：执行子命令后须在 Telnet 侧 **`end`** 回到 enable（模板约定）；否则探测与后续 `show running-config` 会在错误视图。
- **分页**：读循环优先 **`--More--`**，翻页发空格；`_sanitize_cli_pagination` 去掉分页残留。**可选**：`running-config` 中 **`url-group`** 块数 ≤1 时跳过 **`diagnose:ip route show table 100`**。
- **hostname**：设备名在 **`show running-config`** 的 `hostname` 行及提示符前缀体现；采集不下发裸 **`hostname`** CLI（防误入配置子模式）。**`raw_outputs`** 键名与 `parse_all.get(...)` 一致。

---

## 12. deep-dive 报告拓扑链路（2026-05）

- **PC 数据归一化**：`deep_dive.py` 在拓扑构建前，将 `SystemInfoSnapshot` 映射为扁平字段：`hostname`、`primary_ip`、`interfaces`、`os`、`primary_interface`。避免 `TopologyBuilder` 读取旧字段名导致 `pc-001` 显示 `Unknown / N/A`。
- **隧道本地侧地址判定**：`TopologyBuilder` 对 `CPE→Hub` 链路按以下优先级取本地侧：
  1) `show running-config` 中 `interface vxlan* + bind tunnel* + ip address`；  
  2) `show ip route` 中 `vxlan` 接口对应的本地 `/32` 路由；  
  3) WAN/首个可用接口回退。
- **报告展示语义**：`deep_dive.html` 节点增加“上行/下行路径（IP+接口）”，链路一览新增“接口说明（source_interface_name）”列，降低用户对“不同网段地址”的误判。
