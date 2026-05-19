# 日常 Agent 提示词模板

与仓库规则 **v3.1**（P0 / P1 / P2 + DoD）配套，供 Cursor Agent（Chat）复制粘贴。  
规则自动加载见 `.cursor/rules/`；本文件**不会**被 Cursor 当作 Rule 加载，需人工选用或 `@` 引用。

---

## 使用方式

### 1. 工作区（必做）

用 **`sdwan_diagnostic_platform` 文件夹** 作为 Cursor 工作区根（`文件 → 打开文件夹`）。  
若打开的是父目录 `deepseek`，Settings → Rules 里看不到本项目的 3 条 Project Rules。

### 2. 选模板 → 填空 → 发送

1. 看下方 **[场景对照表](#场景对照表)**，选**一种**最接近的模板（不要混用多个完整模板）。
2. 复制对应代码块全文到 Agent 输入框。
3. 把 `<尖括号>` 占位符改成你的实际内容；删去不适用的可选段。
4. 每条任务末尾保留 **[通用约定](#通用约定)**（已内嵌在模板末尾的可不再重复粘贴）。

### 3. 在 Cursor 里引用本文件（可选）

- 输入 `@docs/prompts/DAILY_PROMPTS.md`，再补一句：「按 **模板 X** 执行，填空如下：…」
- 或只 `@` 某一节，避免整文件进上下文。

### 4. 与 Agent 的衔接用语

| 你的意图 | 发送 |
|----------|------|
| 方案通过，开始写码 | `开始实现` |
| 只要方案 | 用 [A4 仅方案](#a4-新增需求--仅方案不写码) |
| 缩小范围 | `本次只做 <X>，其余记入 changelog 待办` |
| 切换功能流 | `current_flow 改为 <流名>，按对应 FLOW_*.md 做` |
| 要求按 DoD 收尾 | `按 DoD 跑 test_map 并首行报 pytest` |
| 禁止扩 scope | `不要重构周边，只修本 issue` |

### 5. 改码前你可手动维护（可选）

- `memory-bank/INDEX.md` 的 **`current_flow`**：与本次任务一致，Agent 会优先读对应 `FLOW_*.md`。
- 大需求建议：**先 A4 仅方案 → 你审 → 再「开始实现」**，省 token、少走偏。

### 6. 完成标准（你怎么判断 Agent 真的做完）

- 回复**首行**为：`pytest: N passed, M failed`（**M 须为 0** 才算测试过关）。
- 若改了 `src/**/*.py`，应有对应 `docs/implementation/src/...` 镜像更新。
- GUI / 实机 / 子进程全链路：Agent 须单独一行 `人工验收: 待办 | 不适用`，不能只用子集单测冒充。

---

## 场景对照表

| 编号 | 场景 | 模板 |
|------|------|------|
| **A1** | 新增功能 / 一般改码 | [A1 新增需求（标准）](#a1-新增需求标准) |
| **A2** | 新增 / 改动三条流（Flow、handlers、CLI/GUI 步骤） | [A2 三条流](#a2-新增需求三条流) |
| **A3** | 新增 / 改动报告、联合诊断、5200B 门控 | [A3 报告与产品口径](#a3-新增需求报告产品口径-p2) |
| **A4** | 新需求只要方案 | [A4 仅方案](#a4-新增需求--仅方案不写码) |
| **B1** | Bug / 行为不符合预期 | [B1 解决问题（标准）](#b1-解决问题标准) |
| **B2** | pytest / CI 失败 | [B2 测试失败](#b2-解决问题测试失败) |
| **B3** | deep-dive / agentctl / 子进程 / GUI 卡住 | [B3 深度诊断](#b3-解决问题深度诊断--agentctl) |
| **B4** | 只要排查根因 | [B4 仅排查](#b4-解决问题--仅排查不写码) |

---

## 通用约定

以下可单独贴在任意模板**末尾**（各模板已含「遵守 P0…」一句时，不必重复）：

```text
遵守 P0（.cursor/rules/sdwan-p0-core.md）。改 flow/runtime/interface/三条流相关 services 前先读 memory-bank/INDEX.md。
勿全文读 AI_SPEC_GUIDE.md、SDWAN_SPEC.md；需要时用 grep 读片段。
改 src 后按 memory-bank/test_map.yaml 推导并执行 pytest；回复首行：pytest: N passed, M failed。
仅当 M=0 且（若改 src）implementation 镜像已同步时，方可写「已完成/验收通过」。
```

---

## A1 新增需求（标准）

适用：新功能、字段、小重构、非三条流专规的模块（collector、parser、工具 Tab 等）。

```text
【新增需求】

背景：
- 用户/场景：<谁在用、什么环境>
- 痛点：<现在缺什么>

目标（可验收）：
- <完成标准 1>
- <完成标准 2>

范围：
- 涉及流：quick-check | deep-dive | business-diagnose | 非流（说明模块）
- 预计改动目录：<例如 src/.../services/...>
- 不在本次：<明确不做>

约束：
- 架构：dataclass/pydantic、{status,data,error}、trace_id、业务层禁 print
- 若触及 flow/runtime/interface/三条流 services：先读 memory-bank/INDEX.md + 一份 FLOW_*.md
- 若触及 diagnosis/reporter/analyzer：先读 docs/rules/INDEX.md
- 改 src/**/*.py 须同步 docs/implementation/src/... 镜像（spec/00_core/implementation_doc_mirror.md）

请先：
1. 读 memory-bank/INDEX.md，声明 current_flow 与将读的 FLOW 文档（三条流时只读一份）
2. 给出 ≤5 步实现计划 + 将 touch 的 src 列表
3. 等我确认或我回复「开始实现」后再改码（若我已说开始实现则直接做）

交付：实现 + 测试；首行 pytest 汇总；GUI/实机单独一行「人工验收: …」

遵守 P0；按 test_map.yaml 跑 pytest；M=0 方可称完成。
```

---

## A2 新增需求（三条流）

适用：改 `flow/`、`runtime/`、`flow/handlers/`、三条流 CLI/GUI、`FlowContext` 步骤与键。

```text
【新增需求 · 三条流】

流：quick-check | deep-dive | business-diagnose

需求：
<一句话功能>

步骤/契约（若已知）：
- 新 Step id：<step-xxx>，depends_on：<…>
- FlowContext.metadata 新键：<key>（须登记 shared_context_keys）
- CLI/GUI 入口：<文件或命令>

禁止：
- CLI/GUI 各写一套等价 step_*；须 handlers/ 或 build_*_step_handlers
- handlers 键与 StepDefinition.id 不一致

请先读：
- memory-bank/INDEX.md
- docs/implementation/FLOW_<当前流>.md
- .cursor/rules/P1-three-flows-shared.md

实现后回复须含 P1 短 checklist（6 条中与本次相关的项，逐条说明）。

遵守 P0；按 test_map.yaml 跑 pytest；M=0 方可称完成。
```

---

## A3 新增需求（报告/产品口径 P2）

适用：联合 HTML、报告字段、Overlay/策略呈现、5200B 门控、business-diagnose UX。

```text
【新增需求 · 报告/产品口径】

需求：
<联合报告字段 / UX / 门控逻辑>

涉及：
- 模块：reporter | diagnosis | analyzer | reporting（路径：<…>）
- 是否 5200B：<是 → 仅 is_raisecom_msg5200b_cpe() 分支；否 → 禁止 presentation 层写厂商专有 if>

请先读：
- docs/rules/THREE_FLOWS_PRODUCT_POSITIONING.md
- docs/rules/BUSINESS_DIAGNOSE_REPORT_UX.md（若联合报告）
- 5200B：docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md

遵守 P0；按 test_map.yaml 跑 pytest；M=0 方可称完成。
```

---

## A4 新增需求 — 仅方案（不写码）

```text
【新增需求 · 仅方案】

背景：<简述>
目标：<可验收标准>
范围：<目录/流>；不做：<…>

请只输出：
- 影响面与风险
- 将 touch 的 src 列表
- 建议阅读的 FLOW / docs/rules 文档（各最多 1～2 个）
- 从 memory-bank/test_map.yaml 推导的 pytest 路径

不要改任何文件。等我回复「开始实现」。
```

---

## B1 解决问题（标准）

```text
【解决问题】

现象：
- 操作路径：<CLI 命令 / GUI Tab / Flow 哪一步>
- 期望：<应该怎样>
- 实际：<报错、日志片段、截图文字>
- 复现：<稳定/偶发；环境/数据要点>

线索（可选）：
- 相关文件：<若已知>
- 最近改动：<功能名或「无」>

请先：grep + 小范围定位根因 → 最小改动修复（Surgical only）。

验证：按 test_map.yaml 跑 pytest；首行 pytest 汇总。
若涉及 GUI/子进程/agentctl：单独「人工验收: …」，勿用子集单测冒充全链路。

遵守 P0；M=0 方可称完成。
```

---

## B2 解决问题（测试失败）

```text
【解决问题 · 测试失败】

失败用例：
<paste：test_xxx.py::test_yyy 与断言摘要>

背景：
- 是否刚改：<文件/功能 或 无>
- 本地命令：python -m pytest <path> -q --tb=short

请：修到 M=0；说明是测试过时还是实现错误；勿扩大改动面。

遵守 P0；首行 pytest: N passed, M failed。
```

---

## B3 解决问题（深度诊断 / agentctl）

```text
【解决问题 · deep-dive / agentctl】

现象：
<子进程超时 / 无输出 / 某 step 卡住 / GUI 无结果>

环境：
- GUI 是否走子进程 agentctl deep-dive：<是/否>
- 单测如需 in-process：可 monkeypatch deep_dive_use_inprocess=True

相关（按需读）：
- flow/definitions/deep_dive.py、handlers/deep_dive_steps.py
- interface/gui/tabs/deep_dive_tab.py、cli/commands/deep_dive.py
- docs/implementation/FLOW_deep_dive.md

请先核对 StepDefinition.id 与 handlers 键是否一致。

遵守 P0；按 test_map.yaml 跑 pytest；M=0 方可称完成。
```

---

## B4 解决问题 — 仅排查（不写码）

```text
【解决问题 · 仅排查】

现象：<…>
复现：<…>

请给出：根因假设（按概率排序）、应读的 2～3 个文件、建议 pytest 路径（test_map 推导）。
不要改代码。等我确认后再修。
```

---

## 填写示例

**示例 A2（deep-dive GUI 摘要）**

```text
【新增需求 · 三条流】

流：deep-dive

需求：GUI 深度诊断完成后，在结果区展示 step-cpe-post-probe 摘要一行。

范围：deep_dive_tab.py；不动 quick-check。

请先读 INDEX + FLOW_deep_dive.md + P1-three-flows-shared.md，给计划后「开始实现」。

遵守 P0；首行 pytest: N passed, M failed。
```

**示例 B1（一键体检误报）**

```text
【解决问题】

现象：
- 路径：GUI 一键体检 → 完成报告
- 期望：DNS 正常时不应标红
- 实际：报告 DNS 段显示失败，CLI 同配置通过
- 复现：稳定；Windows 11，内网 DNS 10.x

请先定位 analyzer/rules 或 quick-check handler，最小修复。

遵守 P0；按 test_map 跑 pytest。
```

---

## 相关入口

| 用途 | 路径 |
|------|------|
| 规则级别地图 | `.cursor/RULES.md` |
| 改码闸门 / current_flow | `memory-bank/INDEX.md` |
| 测试路径映射 | `memory-bank/test_map.yaml` |
| Agent 薄索引 | `AGENTS.md` |
| 规范查阅表（勿全文当规则） | `.cursor/AI_SPEC_GUIDE.md` |
| 产品/报告规则 | `docs/rules/INDEX.md` |

---

## 维护

- 新增场景：在本文件增加一节 + 更新 [场景对照表](#场景对照表)。
- 与 P0/P1 冲突时以 `.cursor/rules/` 为准；模板仅作交互约定，不替代 Rule。
