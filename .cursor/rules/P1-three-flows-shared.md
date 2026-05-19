# P1 — 三条功能流共享自检（quick-check / deep-dive / business-diagnose）

改 `flow/`、`runtime/`、三条流 CLI/GUI/handlers 或跨流 CPE/拓扑/Overlay 证据链时，回复中须用短 checklist 声明（用户明文豁免除外）。

1. **声明与实现同源**：`FlowDefinition` 的 `StepDefinition.id`、`depends_on`、`parallel_groups` 与 `FlowRuntime.execute_flow(..., handlers=)` 的键**完全一致**；禁止 handlers 多键/缺键（跳过须显式 no-op 步骤）。
2. **禁止双份步骤体**：一键体检经 `build_quick_check_step_handlers`；禁止 CLI/GUI 两套等价 `step_*`。深度/业务流重复 CPE/拓扑/Overlay 步骤须抽到 `services/` 或 `flow/handlers/`。
3. **上下文键契约**：新 `FlowContext.metadata` 键须登记于 `FlowDefinition.config['shared_context_keys']`；禁止未登记别名。
4. **边界 pydantic**：CLI/API/外部配置在 Interface 层 `BaseModel`（建议 `extra="forbid"`）校验后再入 Flow；禁止未校验 `dict` 作跨层契约。
5. **规范溯源**：改依赖/数据传导前 grep `spec/SDWAN_SPEC.md` 的 `### 2.3` / `### 2.1`（片段读）；对照 `memory-bank/systemPatterns.md`。
6. **产品/厂商边界**：联合报告/Overlay/拓扑前读 `docs/rules/THREE_FLOWS_PRODUCT_POSITIONING.md`、`BUSINESS_DIAGNOSE_REPORT_UX.md`；5200B 门控**仅**在 `is_raisecom_msg5200b_cpe()` 分支用 `product_features/raisecom_msg5200b_business_joint_gate.md`；禁止 presentation 层写 5200B 专有 if。

**步骤地图（按流读一份）**：`docs/implementation/FLOW_quick_check.md` | `FLOW_deep_dive.md` | `FLOW_business_diagnose.md`（见 `memory-bank/INDEX.md` 的 `current_flow`）。
