---
description: SD-WAN 项目必守（P0）— DoD、架构契约、闸门与禁止项
alwaysApply: true
---

# P0 必守（本仓库）

行为全文（B0）：`.cursor/cursor_code_skills.md`。级别地图：`.cursor/RULES.md`。

## B0 摘要（12 条一行）

Think first | Simplicity | Surgical only | Goal+verify | Model=judgment | Token budget | Surface conflicts | Read before write | Tests=intent | Checkpoint | Match repo | Fail loud

## P0 架构八条

1. 跨层：`dataclass`/`pydantic`；禁裸 `dict` 跨层。
2. 返回：`{status, data, error}`。
3. 日志：`logging`；业务层禁 `print`。
4. 全链路含 `trace_id`。
5. 公开函数：类型注解 + docstring。
6. 依赖注入；禁内部硬编码单例。
7. 网络分析相关新改：`services/diagnosis|analyzer|reporter`、联合 CLI/GUI：注释+docstring ≈≥30% 非空行；关键启发式注明 `docs/rules`/`spec` 依据。
8. 改 `src/**/*.py` 须同步 `docs/implementation/src/.../*.md`（见 `spec/00_core/implementation_doc_mirror.md`）。

## DoD（改码结束必做，优先于一切“测试输出格式”）

1. 列出本轮 touched 的 `src/**`。
2. `memory-bank/test_map.yaml` 推导 pytest 路径；改码收敛后**执行一次**。
3. 回复**首行**：`pytest: N passed, M failed`；失败仅列用例名+断言（≤3 行/条）。
4. Plan 实机项单独一行：`人工验收: 待办 | 不适用`；禁子集单测冒充。
5. **仅当 M=0** 且（若改 src）implementation 镜像已更新，方可写「已完成/验收通过」。

## 闸门（L1）

改 `interface/`、`flow/`、`runtime/`、三条流相关 `services/` → 先读 `memory-bank/INDEX.md`（≤80 行）。**禁**用 `activeContext.md` 作闸门；**禁**常规读 `progress.md`。

## 禁止

- 全文读 `AI_SPEC_GUIDE.md`、全文 `SDWAN_SPEC.md`、`progress.md`、无触发遍历 `product_features/`。
- 无新变更重复跑同一 pytest。

## 工具效率

先 grep/定位 → `read_file` 带 offset/limit（默认≤400 行/次）；独立只读并行；同文件相关改动合并补丁。

## 冲突优先级

DoD + B0 Fail loud > P1 流自检 > P2 产品口径 > spec 片段。
