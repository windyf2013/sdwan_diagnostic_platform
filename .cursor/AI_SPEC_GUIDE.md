# AI 规范索引（已瘦身 — 非闸门文件）

> **勿全文当作规则读。** 必守见 `.cursor/rules/sdwan-p0-core.md`（P0）。行为见 `.cursor/cursor_code_skills.md`（B0）。  
> 三条流自检见 `.cursor/rules/P1-three-flows-shared.md`（P1 glob 自动挂载）。  
> 改码闸门：`memory-bank/INDEX.md`。级别地图：`.cursor/RULES.md`。

## 补丁

- 修订条款唯一正文：`spec/SDWAN_SPEC_PATCHES.md`（高于 `spec/SDWAN_SPEC.md` 冲突处）

## 文档查阅（按需 grep + offset/limit）

| 问题 | 目标 | 关键词示例 |
|------|------|------------|
| 架构/依赖 | `spec/SDWAN_SPEC.md` | `### 1.2`, `### 1.3.1` |
| 工具/流程 | `spec/SDWAN_SPEC.md` | `### 2.4`, `### 2.3` |
| 三条流实现 | `docs/implementation/FLOW_*.md` | 见 INDEX `current_flow` |
| 产品/厂商 | `docs/rules/INDEX.md` | — |
| 详细设计 | `spec/detail_function_design.md` | 章节号 |
| 实现镜像 | `spec/00_core/implementation_doc_mirror.md` | — |
| 任务计划 | `spec/developing_tasks.md` | Sprint 节 |

## CLI 参数命名（click）

- 长选项：`--kebab-case` 全词；每语义一个规范长名
- 短选项：单 `-` + 单字母；易混用大写（如 `-P` 协议 vs `-p` 端口）
- help 写清默认值与单位

## Memory Bank

- **闸门**：`memory-bank/INDEX.md`
- **历史**：`changelog.md`
- **里程碑**：`progress.md`（仅里程碑时读）
- 更新触发：见 `memory-bank/project_memory.md`

## 测试汇报（§2 输出）

- 首行 `pytest: N passed, M failed`；失败≤3 行/条；禁长篇测试过程总结（用户要求分析时除外）
