---
description: P1 三条功能流 — Flow/handlers/FlowContext 契约与自检（quick-check, deep-dive, business-diagnose）
globs: src/sdwan_desktop/flow/**,src/sdwan_desktop/runtime/**,src/sdwan_desktop/interface/cli/commands/**,src/sdwan_desktop/interface/gui/tabs/**,src/sdwan_desktop/interface/gui/cli_runner.py,src/sdwan_desktop/flow/handlers/**
alwaysApply: false
---

# P1 三条功能流（glob 自动挂载）

1. 读 `.cursor/rules/P1-three-flows-shared.md`，回复短 checklist。
2. 读 `memory-bank/INDEX.md` 的 `current_flow`，再读对应 **一份** `docs/implementation/FLOW_*.md`。
3. **禁止**为三条流去读 `AI_SPEC_GUIDE.md` 全文；细节用 `spec/SDWAN_SPEC.md` grep `### 2.3`。

一键体检用户可见输出可用 `QuickCheckHandlersParams.console`（与业务层禁 `print` 不冲突）。
