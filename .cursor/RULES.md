# 规则级别地图（B0 / P0 / P1 / P2 / L）

给人与 Agent 的对照表。Cursor 加载方式见各文件 frontmatter。

| 级别 | 含义 | 文件 | 加载 |
|------|------|------|------|
| **B0** | 核心行为准则 | `.cursor/cursor_code_skills.md` | P0 内摘要；全文按需 |
| **P0** | 项目必守（DoD、八条、禁止） | `.cursor/rules/sdwan-p0-core.md` | **alwaysApply** |
| **P1** | 三条流开发专规 | `P1-three-flows-shared.md` + `FLOW_*.md` | **globs** 自动挂载 |
| **P2** | 产品/厂商/报告 UX | `docs/rules/**` | **globs** + INDEX |
| **L1** | 冲刺索引 | `memory-bank/INDEX.md` | 改码闸门 |
| **L2** | spec / implementation | `spec/`, `docs/implementation/` | grep 片段 |

## 维护约定（防回头路）

- **禁止**把三条流自检写回 `AI_SPEC_GUIDE.md` 正文（`scripts/lint_cursor_rules.py` 会拦）
- **禁止**扩写 `activeContext.md`；历史写 `changelog.md`
- 扩大规则优先：新 **P2** 进 `docs/rules/`；新 **P1** 进 `P1-three-flows-shared` 或 `FLOW_*.md`
- 仅 **一个** `alwaysApply: true` 的 P0 文件（≤120 行）

## 冲突优先级

DoD + B0 Fail loud > P1 > P2 > spec 片段

## 日常交互

Agent 提示词模板（新增需求 / 排障）：[`docs/prompts/DAILY_PROMPTS.md`](../docs/prompts/DAILY_PROMPTS.md)
