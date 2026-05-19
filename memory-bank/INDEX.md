# L1 — 项目索引（改码闸门，保持 ≤80 行）

## 当前冲刺

- **Sprint 8** — 发布准备（阶段 8.4 发布回归）
- **版本**: 1.0.0-rc1

## current_flow

- **primary**: `deep-dive`（`quick-check` | `deep-dive` | `business-diagnose` | `multi`）
- **also**: []

## 当前焦点

- 深度诊断 GUI 默认子进程 `agentctl deep-dive`；Flow v1.2.0 九步（`step-biz-probe` / `step-cpe-post-probe`）
- 规则体系 v3.1：`.cursor/rules/sdwan-p0-core.md`（P0 MUST）+ P1/P2 glob 规则

## 文件映射（三条流 / CPE / 报告）

| 模块 | 路径 |
|------|------|
| Flow 定义 deep-dive | `src/sdwan_desktop/flow/definitions/deep_dive.py` |
| Flow handlers | `src/sdwan_desktop/flow/handlers/deep_dive_steps.py` |
| 深度诊断 CLI | `src/sdwan_desktop/interface/cli/commands/deep_dive.py` |
| 深度诊断 GUI | `src/sdwan_desktop/interface/gui/tabs/deep_dive_tab.py` |
| CPE 采集 | `src/sdwan_desktop/services/collector/cpe_collector.py` |
| 5200B 解析 | `src/sdwan_desktop/services/parser/vendor/raisecom_msg5200b.py` |
| 业务诊断 CLI | `src/sdwan_desktop/interface/cli/commands/business_diagnose.py` |
| 联合报告载荷 | `src/sdwan_desktop/services/reporter/joint_commercial_delivery.py` |

## 流程地图（P1，读一份）

- quick-check → `docs/implementation/FLOW_quick_check.md`
- deep-dive → `docs/implementation/FLOW_deep_dive.md`
- business-diagnose → `docs/implementation/FLOW_business_diagnose.md`

## 规则入口

| 级别 | 文件 |
|------|------|
| B0 | `.cursor/cursor_code_skills.md` |
| P0 | `.cursor/rules/sdwan-p0-core.md` |
| P1 | `.cursor/rules/P1-three-flows-shared.md` + 上表 FLOW |
| P2 | `docs/rules/INDEX.md` |
| 地图 | `.cursor/RULES.md` |
| 日常 Prompt | `docs/prompts/DAILY_PROMPTS.md` |

DoD 测试映射：`memory-bank/test_map.yaml`。

历史变更见 `memory-bank/changelog.md`。里程碑见 `progress.md`（勿作每轮闸门）。
