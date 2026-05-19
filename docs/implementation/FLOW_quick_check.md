# 流程地图：一键体检（quick-check）

面向 Agent / 维护者：先读本文再按需下钻 [`SRC_INDEX.md`](SRC_INDEX.md) 与 [`docs/implementation/src/`](./src/) 单文件说明。

---

## 入口与命令

| 入口 | 路径 |
|------|------|
| CLI 主命令 | [`src/sdwan_desktop/interface/cli/commands/quick_check.py`](../../src/sdwan_desktop/interface/cli/commands/quick_check.py)（`sdwan-quick-check` / `agentctl` 子命令） |
| GUI 标签页 | [`src/sdwan_desktop/interface/gui/tabs/quick_check_tab.py`](../../src/sdwan_desktop/interface/gui/tabs/quick_check_tab.py) |
| 控制台脚本 | [`pyproject.toml`](../../pyproject.toml) `project.scripts` → `quick_check` |

---

## FlowDefinition 与 handlers

| 资源 | 路径 |
|------|------|
| 流程图（步骤 id、`depends_on`、`parallel_groups`） | [`src/sdwan_desktop/flow/definitions/quick_check.py`](../../src/sdwan_desktop/flow/definitions/quick_check.py) 中 `QUICK_CHECK_FLOW` |
| **唯一** handler 工厂（禁止 CLI/GUI 各写一套大段 `step_*`） | [`src/sdwan_desktop/flow/handlers/quick_check_steps.py`](../../src/sdwan_desktop/flow/handlers/quick_check_steps.py) `build_quick_check_step_handlers` |
| 运行时 | [`src/sdwan_desktop/runtime/engine.py`](../../src/sdwan_desktop/runtime/engine.py) `FlowRuntime.execute_flow` |

CLI/GUI 均构造 `QuickCheckHandlerDeps` + `QuickCheckHandlersParams`，传入工厂得到 `handlers` 字典，键名须与 `QUICK_CHECK_FLOW` 中各 `StepDefinition.id` **完全一致**。

---

## 跨步骤数据键（FlowContext）

权威列表见 `QUICK_CHECK_FLOW.config["shared_context_keys"]`，主要包括：

`system_snapshot`、`dns_results`、`gateway_ping_result`、`internet_connectivity_result`、`dns_resolution_cache`、`tcping_results_cache`、`traceroute_results_cache`、`unified_domain_set`、`test_mode`、`dns_split_result`、`cpe_link_routing_result`、`diagnosis_result`。

写入 `metadata` 的新键须登记到 `shared_context_keys`（见 `.cursor/AI_SPEC_GUIDE.md`「架构与三条功能流」）。

---

## 证据与报告

| 能力 | 典型路径 |
|------|-----------|
| 系统采集 | `services/collector/windows_collector.py` |
| 连通性 / DNS 服务器 / 互联网优化探测 | `services/connectivity.py` |
| DNS 分流与 CPE 链路路由（含 traceroute 预算） | `services/dns_split.py` |
| 规则引擎与规则包 | `services/analyzer/rule_engine.py`、`services/analyzer/rules/` |
| HTML / JSON 报告 | `services/reporter/html_builder.py`、模板 `reporting/templates/quick_check.html` |

一键体检 HTML 用户可见输出由 `QuickCheckHandlersParams.console` 等控制；业务层禁止 `print`（规范见 `AI_SPEC_GUIDE`）。

---

## 相关 spec / docs/rules

| 文档 | 用途 |
|------|------|
| [`spec/detail_function_design.md`](../../spec/detail_function_design.md) | 一键体检规则、成功判据、JSON 载荷等 |
| [`spec/SDWAN_SPEC.md`](../../spec/SDWAN_SPEC.md) | 流程与数据契约 |
| [`docs/rules/INDEX.md`](../rules/INDEX.md) | 产品特性与规则索引 |

---

## 单文件深描索引

下钻时打开 [`SRC_INDEX.md`](SRC_INDEX.md) 定位 `.py`，再打开镜像文档 `docs/implementation/src/.../同名.md`（若尚未建立则按 `spec/00_core/implementation_doc_mirror.md` 补齐）。

高频文件：`flow/definitions/quick_check.py`、`flow/handlers/quick_check_steps.py`、`interface/cli/commands/quick_check.py`、`services/dns_split.py`、`services/connectivity.py`、`services/analyzer/rule_engine.py`。
