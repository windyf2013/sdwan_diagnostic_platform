# 流程地图：深度诊断（deep-dive）

面向 Agent / 维护者：先读本文再按需下钻 [`SRC_INDEX.md`](SRC_INDEX.md) 与 [`docs/implementation/src/`](./src/) 单文件说明。

---

## 入口与命令

| 入口 | 路径 |
|------|------|
| CLI | [`src/sdwan_desktop/interface/cli/commands/deep_dive.py`](../../src/sdwan_desktop/interface/cli/commands/deep_dive.py)（`sdwan-deep-dive`） |
| GUI | [`src/sdwan_desktop/interface/gui/tabs/deep_dive_tab.py`](../../src/sdwan_desktop/interface/gui/tabs/deep_dive_tab.py)（默认 `AgentctlWorker` 子进程；`SDWAN_DEEP_DIVE_INPROCESS=1` 回退 `DeepDiveWorker`） |

---

## FlowDefinition 与 handlers

| 资源 | 路径 |
|------|------|
| 流程定义 | [`src/sdwan_desktop/flow/definitions/deep_dive.py`](../../src/sdwan_desktop/flow/definitions/deep_dive.py) `DEEP_DIVE_FLOW`（v1.2.0，9 步） |
| 步骤实现 | [`src/sdwan_desktop/flow/handlers/deep_dive_steps.py`](../../src/sdwan_desktop/flow/handlers/deep_dive_steps.py) `build_deep_dive_step_handlers` / `run_deep_dive_flow` |
| 运行时 | [`src/sdwan_desktop/runtime/engine.py`](../../src/sdwan_desktop/runtime/engine.py) `FlowRuntime.execute_flow` |

步骤顺序：PC 采集 → CPE 连接 → CPE 采集（180s）→ 拓扑构建 → **PC 业务探测**（300s）→ **CPE 拓扑后补采**（180s）→ Overlay 证据链 → 根因分析 → 报告生成。

**CLI / GUI 默认一致**：省略 `-b` 时注入三域 `baidu/youtube/tiktok`；**均默认启用 traceroute**（GUI 不传 `--no-traceroute`）。

**拓扑后探测拆步**：原 `step-targeted-probe` 拆为 `step-biz-probe` + `step-cpe-post-probe`，降低单步 360s 触顶失败率；`targeted_probe_pc` 为中间键（见 `shared_context_keys`）。

---

## 跨步骤数据键（FlowContext）

`shared_context_keys`：`overlay_policy_flow`、`targeted_probe`、`targeted_probe_pc`、`cpe_result`。

---

## GUI 性能（2026-05）

- 默认与 CLI 同宿主：`agentctl deep-dive` 子进程 + `[n/9]` 进度（[`cli_runner.py`](../../src/sdwan_desktop/interface/gui/cli_runner.py) 子进程总超时 660s）。
- 回归：同 CPE、同凭证、均启用 traceroute，CLI vs GUI 墙钟中位数差距目标 &lt;15%。

---

## 相关 spec / docs/rules

| 文档 | 用途 |
|------|------|
| [`spec/detail_function_design.md`](../../spec/detail_function_design.md) | 深度诊断、解析器、探测与 CLI 章节 |
| [`docs/rules/product_features/`](../rules/product_features/) | 厂商行为与 Overlay 口径（如 5200B） |

---

## 单文件深描索引

使用 [`SRC_INDEX.md`](SRC_INDEX.md) 查找 `deep_dive_steps.py`、`cpe_collector.py`、`deep_dive_tab.py` 等对应 `docs/implementation/src/.../*.md`。
