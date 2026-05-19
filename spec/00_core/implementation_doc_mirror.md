# 功能实现文档镜像规范（Implementation Doc Mirror）

**文档编号**: IDM-001  
**规范等级**: Mandatory（与 `.cursor/AI_SPEC_GUIDE.md` 核心强制约束第 8 条一致）  
**适用范围**: 工程根目录下 `src/` 树内、纳入版本控制的**可执行实现**（以 Python 源码为主；其它类型见下文触发条件）。

---

## 1. 目标与边界

### 1.1 目标

- 为每一处 `src/` 实现维护**工程内可追溯**的「功能实现说明」，便于评审、交接与排障时快速对照代码行为，而不替代 `spec/` 中的架构契约与领域规范。

### 1.2 与 `spec/`、`docs/rules/` 的分工

| 层级 | 存放位置 | 回答的问题 |
|------|-----------|------------|
| 架构与契约 | `spec/`（如 `SDWAN_SPEC.md`、`detail_function_design.md`） | 系统**必须**如何表现、数据与流程契约 |
| 产品与现网口径 | `docs/rules/`、`docs/rules/product_features/` | 设备行为与诊断**口径** |
| **单文件实现说明** | `docs/implementation/src/...`（本规范） | 本文件**如何实现**、关键分支、依赖与证据链 |

实现文档**必须**引用相关 `spec/` 或 `docs/rules/` 条款（若存在），避免重复粘贴大段契约正文。

---

## 2. 路径映射（一比一）

### 2.1 基本规则（MUST）

设工程根目录为 `<root>`（本仓库即 `sdwan_diagnostic_platform/`）。

- 对任意源码文件：`<root>/src/<REL>/<NAME>.<EXT>`  
- 对应功能实现文档：`<root>/docs/implementation/src/<REL>/<NAME>.md`

其中 `<REL>` 为相对 `src/` 的目录路径（可为空）；`<EXT>` 为下文「纳入镜像」列表中的扩展名；目标一律为 **UTF-8 Markdown（`.md`）**。

**示例**

| 源码 | 功能实现文档 |
|------|----------------|
| `src/sdwan_desktop/services/probe/planner.py` | `docs/implementation/src/sdwan_desktop/services/probe/planner.md` |
| `src/sdwan_desktop/interface/cli/commands/quick_check.py` | `docs/implementation/src/sdwan_desktop/interface/cli/commands/quick_check.md` |

### 2.2 纳入镜像的扩展名（MUST）

- `.py`

### 2.3 条件纳入（CONDITIONAL → MUST）

满足任一条件时，**必须**为对应文件建立或更新镜像 `.md`（映射规则同 2.1，扩展名替换为 `.md`）：

- `.pyi`（公共类型桩与对外契约说明）
- 含**非平凡逻辑**的 `*.sql`、`*.sh`、或其它被应用**直接执行/加载**的脚本（若未来出现在 `src/` 下）

### 2.4 默认不强制逐文件镜像（SHOULD 用「就近 Python 文档」覆盖）

以下类型**不**要求与每个文件严格同名 `.md`；**必须**在**负责渲染或组装的最近一层 Python 模块**的实现文档中增加独立章节「非 Python 资产说明」，列出路径、变量块、与上下游数据流：

- HTML / Jinja / 静态模板（如 `*.html`）
- 纯样式、图片、字体等前端静态资源

若某模板被多个 Python 入口复用且语义分叉，SHOULD 拆章节或子列表标明调用方文件。

---

## 3. 文档内容与模板（MUST 结构）

每个 `docs/implementation/src/.../*.md` **必须**包含以下区块（允许合并小节，但信息不得缺失）：

1. **元数据（文件头）**  
   - `对应源码`：仓库内相对路径（从 `src/` 或从根目录写清其一并全文一致）。  
   - `最近更新`：日期（`YYYY-MM-DD`）与变更摘要一句。  
   - `关联规范`：链接或路径到 `spec/`、`docs/rules/` 相关条目（无则写「无，以代码契约为准」）。

2. **职责概述**  
   - 本模块在分层中的角色（Interface / Flow / Service / Tool / Core 等，与 `spec/SDWAN_SPEC.md` 一致）。

3. **对外接口**  
   - 主要公开符号（类/函数/CLI 子命令入口）：签名级说明、副作用、线程/异步语义。

4. **关键逻辑与分支**  
   - 与诊断结论、报告文案、拓扑或证据链相关的分支；启发式须写明依据文档或假设。

5. **依赖与数据流**  
   - 主要入参/上下文键/调用的下游模块；写出向 `FlowContext.metadata` 或报告载荷的写入字段名（若适用）。

6. **测试与验证**  
   - 指向关键单测或 flow 测路径（`tests/...`）；若无测例，须注明「待补」与风险。

### 3.1 `__init__.py` 的精简写法（ALLOWED）

若文件仅为 re-export 且无业务逻辑，实现文档允许少于 20 行，但**仍须**包含：元数据、职责一行、`__all__` 或导出表、关联规范链接。

---

## 4. 触发时机（MUST）

以下变更**同一交付单元内**必须创建或更新对应镜像 `.md`（允许与代码同一 PR / 同一连续子任务）：

1. **新增** `src/` 下受 2.2、2.3 约束的源文件。  
2. **实质性修改**既有实现：行为、默认值、CLI 参数、对外 JSON/HTML 字段、根因或证据链语义发生变更。  
3. **重命名或移动**源文件：须**移动/重命名**对应 `.md` 并保持路径映射，禁止遗留失效链接。

**豁免（需在同一 PR 或 activeContext 中写明理由）**：仅错别字、注释笔误、格式化、未改变行为的类型注解收紧。

---

## 5. 质量门禁（SHOULD → 推荐落地为 CI）

- **MUST（仓库已落地）**：当变更触及 `.pre-commit-config.yaml` 中 `implementation-src-index` 钩子的 `files` 模式（`src/`、`docs/implementation/src/`、`docs/implementation/src_roles.yaml`、生成脚本）时，**须**在提交前运行 `python scripts/generate_implementation_index.py` 并提交更新后的 `docs/implementation/SRC_INDEX.md`；钩子以 `--check` 比对，不一致则**阻断提交**。亦可使用 **`python scripts/prepare_git_commit.py --auto-add-index`** 一次完成再生与暂存（仍须自行 `git commit`），或使用 `scripts/git-commit.ps1` / `scripts/git-commit.sh` 串联提交。
- **SHOULD**：CI 或额外 pre-commit 对「本 MR 改动的 `src/**/*.py`」做存在性检查：对应 `docs/implementation/src/**/*.md` 是否存在且非空（可排除明确标注的生成代码目录，若有）。  
- **MUST（人工评审）**：合并前检查实现文档中的「关联规范」链接是否仍有效。

---

## 6. 指引条款（给 Agent / 评审人）

1. 改 `src/` 前先查是否已有镜像文档；若无且本次为新增/实质修改，**先**在 `spec/` 确认契约，**再**写代码与镜像文档。  
2. 镜像文档**禁止**粘贴密钥、生产主机名、完整客户配置；示例用占位符。  
3. 与 `memory-bank/activeContext.md` 中的「当前冲刺文件映射表」同步登记新增或高频修改的镜像路径，便于按需 `read_file`。  
4. 若用户明确豁免本规范的某条，须在回复或 PR 描述中**逐条**写出豁免项与原因。
5. **导航顺序（强制）**：涉及三条功能流时，先读 `docs/implementation/FLOW_<flow>.md`（quick-check / deep-dive / business-diagnose）建立链路心智模型，再读 `docs/implementation/SRC_INDEX.md` 定位路径，再打开 `docs/implementation/src/...` 单文件镜像，最后按需 `read_file` 局部源码。
6. **`SRC_INDEX.md` 为生成物**：禁止手工改表体；路径与「ImplDoc」列以脚本为准；职责列通过 `src_roles.yaml` 或镜像文档 `## 职责概述` 维护。

---

## 7. 实现层导航（流程地图与索引）

| 层级 | 路径 | 作用 |
|------|------|------|
| 一键体检流程地图 | `docs/implementation/FLOW_quick_check.md` | 入口、Flow、handler 工厂、共享键、报告链路 |
| 深度诊断流程地图 | `docs/implementation/FLOW_deep_dive.md` | 同上；附录 waterfall |
| 业务路径诊断流程地图 | `docs/implementation/FLOW_business_diagnose.md` | 同上；联合前置与退出码 2 |
| 全树路径索引（自动生成） | `docs/implementation/SRC_INDEX.md` | 每个 `src/` 文件的 ImplDoc 状态与职责摘要列 |
| 人工热点摘要（可选） | `docs/implementation/src_roles.yaml` | 覆盖 `SRC_INDEX` 中「Role / Summary」列 |

---

## 8. 修订记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-05-15 | v1.0 | 初版：路径映射、模板、触发条件与指引 |
| 2026-05-15 | v1.1 | 增加实现层导航、`SRC_INDEX` 门禁与 Agent 阅读顺序 |
