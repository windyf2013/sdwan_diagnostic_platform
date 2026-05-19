# Agent 指令（薄索引）

本仓库 SD-WAN 诊断平台。细则在 `.cursor/rules/` 与 `memory-bank/INDEX.md`。

## 测试

```bash
cd sdwan_diagnostic_platform
python -m pytest <paths> -q --tb=short
```

改码后按 `memory-bank/test_map.yaml` 推导路径；完成前首行汇报 `pytest: N passed, M failed`。

## 必守

- `.cursor/rules/sdwan-p0-core.md`（P0，always apply）
- 三条流：`.cursor/rules/P1-three-flows-shared.md` + 一份 `docs/implementation/FLOW_*.md`

## 入口

- 规则地图：`.cursor/RULES.md`
- 改码索引：`memory-bank/INDEX.md`
- 日常 Prompt 模板：`docs/prompts/DAILY_PROMPTS.md`
- 架构规范：`spec/SDWAN_SPEC.md`（grep，勿全文）
