# AI 开发速查卡（SD-WAN 诊断专家）

> **协议**：本文件是唯一常驻规则。详细设计请通过工具按需读取 `spec/` 目录。

<system-reminder>

**强制步骤**：在回答任何涉及具体实现、配置、规则的问题前，你必须先执行：
1. `read_file("memory-bank/activeContext.md")`
2. 根据返回的索引调用相应的 `read_file` 查询 `spec/` 下的文档。
3. 请严格遵守 .clinerules 中的文件访问限制和测试输出控制。
如果你没有执行上述步骤就直接生成代码，将被视为严重违规。

</system-reminder>

## 核心强制约束（违反即阻断）
1. 数据结构：跨层传递必须使用 `dataclass` 或 `pydantic`；禁止裸 `dict` 跨层。
2. 返回格式：`{status, data, error}`。
3. 日志：使用 `logging`，禁止 `print`。
4. 全链路：所有对象必须包含 `trace_id`。
5. 类型注解：所有公开函数必须有类型注解和 docstring。
6. 依赖注入：通过构造函数或参数传递依赖，禁止内部硬编码实例化。

## 补丁文件
- `SDWAN_SPEC_PATCHES.md` 与本文档同级，包含覆盖率阈值、dict 豁免等修订条款，**优先级高于原规范**。

## 文档查阅协议（必须遵守）
遇到具体实现问题时，**必须使用 `read_file` 工具按需检索**，严禁一次性加载全文。

| 问题类型 | 查阅目标 | 搜索关键词示例 |
|----------|---------|---------------|
| 架构分层、依赖方向 | `spec/SDWAN_SPEC.md` | `### 1.2 架构原则`, `### 1.3.1 依赖规则` |
| 工具实现规范 | `spec/SDWAN_SPEC.md` | `### 2.4 工具系统规范` |
| 流程编排规范 | `spec/SDWAN_SPEC.md` | `### 2.3 流程规范` |
| 一键体检规则列表 | `spec/detail_function_design.md` | `### 1.3 异常判断规则详细设计` |
| 深度诊断配置解析 | `spec/detail_function_design.md` | `### 2.2 厂商解析器实现` |
| 当前开发任务计划 | `spec/developing_tasks.md` | `## 4. Sprint 3` 或具体任务 ID |
| 项目整体架构说明 | `spec/sdwan_analyzer_project.md` | `## 2. 架构设计` |

## Memory Bank 工作流
1. **开始任务前**：读取 `memory-bank/activeContext.md` 确认当前冲刺和焦点。
2. **完成任务后**：更新 `memory-bank/progress.md` 和 `activeContext.md`。
3. 详细说明见 `memory-bank/project_memory.md`。

## 代码模板参考
- 工具模板：`templates/tool_template.py`（如不存在，按装饰器模式手写）
- 流程模板：`templates/flow_template.py`

## 附加行为约束（Cline 专用）

### 1. 文件系统访问限制
**原则**：避免全量遍历目录，仅访问任务直接相关的文件。

- **启动任何开发任务时**，必须首先执行：
  1. `read_file("memory-bank/activeContext.md")`
  2. 解析其中的 **“📁 当前冲刺文件映射表”**，获取与任务相关的文件路径。
- **后续操作**：
  - 直接使用 `read_file` 打开映射表中的指定文件，不得使用 `search_file` 或 `search_content` 进行全局扫描。
  - 若所需文件不在映射表中，才允许使用 `list_files` 但**必须限制深度为 2**，且仅针对特定子目录（如 `src/sdwan_desktop/services/analyzer/rules/`）。
- **禁止行为**：
  - 禁止使用 `list_files` 递归遍历整个项目目录（尤其是 `src/`、`spec/` 的深度扫描）。
  - 禁止在每次对话开始时无目标地读取多个文件以“了解项目结构”。
- **必须遵守**：
  - 首先读取 `memory-bank/activeContext.md` 获取当前任务的**焦点模块和文件清单**。
  - 若需定位某个功能实现，优先在 `activeContext.md` 中查找已记录的**文件路径映射表**（见下方示例）。
  - 如需读取规范文档，严格按照本文件中的“文档查阅协议”进行**关键词搜索**，而非全文加载。
  - 若确实需要了解目录结构，优先读取项目根目录的 `README.md` 或 `memory-bank/techContext.md` 中记录的**架构概览**，而非实时遍历。

- **推荐做法**：在 `memory-bank/activeContext.md` 中维护一个 **“当前冲刺文件映射表”**，例如：
| 功能模块 | 核心文件路径 |
|---------|-------------|
| 规则引擎 | `src/sdwan_desktop/services/analyzer/rule_engine.py` |
| 网关规则 | `src/sdwan_desktop/services/analyzer/rules/gateway.py` |
| 探测结果类型 | `src/sdwan_desktop/core/types/probe.py` |

### 2. 测试验证阶段输出控制
**原则**：聚焦关键信息，避免冗长过程叙述。

- **在测试验证阶段（即用户要求运行测试、调试、验证功能时）**：
  - **禁止**输出长篇的“测试过程总结”、“阶段性方案调整说明”、“多轮迭代计划”。
  - **允许**输出的内容仅限于：
    - 测试是否通过（PASS/FAIL）。
    - 失败的测试名称和断言错误信息（精简，不超过 3 行/条）。
    - 单条关键修复建议（如有明确方案）。
    - 简要的下一步操作（一句话）。

- **禁止模式示例**：
  ```text
  "根据第一轮测试结果，我们发现...，因此我计划调整方案为...，接下来我将分三步进行..."
  ```

- **推荐输出格式**：
  ```text
   15 passed, 2 failed.
   FAIL: test_gateway_unreachable - AssertionError: severity != CRITICAL
   FAIL: test_dns_timeout - Timeout > 2000ms
   建议：检查 GW-001 规则中的 confidence 阈值配置。
   下一步：修复上述两个失败用例。
  ```

- **例外情况**：
  - 当用户明确要求“分析测试报告”或“制定修复计划”时，才允许展开详细讨论。
