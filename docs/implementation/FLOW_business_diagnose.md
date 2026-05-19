# 流程地图：业务路径诊断（business-diagnose）

面向 Agent / 维护者：先读本文再按需下钻 [`SRC_INDEX.md`](SRC_INDEX.md) 与 [`docs/implementation/src/`](./src/) 单文件说明。

---

## 入口与命令

| 入口 | 路径 |
|------|------|
| CLI | [`src/sdwan_desktop/interface/cli/commands/business_diagnose.py`](../../src/sdwan_desktop/interface/cli/commands/business_diagnose.py)（`sdwan-business-diagnose`） |
| GUI | [`src/sdwan_desktop/interface/gui/tabs/business_diagnose_tab.py`](../../src/sdwan_desktop/interface/gui/tabs/business_diagnose_tab.py) |

业务目标以 `FQDN:端口` 等形式传入；默认对**首个**解析 IPv4 追加一次 **ICMP traceroute**（路径旁证，不单独触发须联合）；可用 `--no-traceroute` 跳过。`step-biz-probe` 步骤超时 **240s**（多 A 记录 TCP 与单次 traceroute 预算）。联合 CPE 需 `--cpe-host` 与 `--username` 等（与深度诊断凭证模型对齐）。**DNS/TCP** 探测失败且未 `--allow-probe-only` 时缺少 CPE 参数将 **退出码 2**（见命令 help 与 `step_validate_joint_prereq`）。

---

## FlowDefinition 与 handlers

| 资源 | 路径 |
|------|------|
| 流程定义 | [`src/sdwan_desktop/flow/definitions/business_diagnose.py`](../../src/sdwan_desktop/flow/definitions/business_diagnose.py) `BUSINESS_DIAGNOSE_FLOW` |
| 步骤实现（内联 `step_*`） | [`src/sdwan_desktop/interface/cli/commands/business_diagnose.py`](../../src/sdwan_desktop/interface/cli/commands/business_diagnose.py) |
| 联合阶段复用逻辑 | `run_joint_root_cause_after_business_probe` 等与 `services/diagnosis/business_diagnose_followup.py` 同源路径 |

联合 HTML 拓扑剖面由 [`topology_joint_presentation.resolve_joint_topology_presentation`](../../src/sdwan_desktop/services/reporter/topology_joint_presentation.py) 统一决策：**若门控/拓扑/旁证表明声明业务与 Overlay/隧道面存在观测关联，则展示 sdwan 剖面及 Overlay 条带（与本次探测是否通过无关）**；详见 [`topology_joint_presentation.md`](./src/sdwan_desktop/services/reporter/topology_joint_presentation.md)。

`handler` 字符串到可调用对象的映射在 CLI 文件中的 `handlers` 字典完成；`handler="diagnosis.business_joint_followup"` 对应步骤体在 CLI 内实现为 `step_joint`（命名以流程定义 id `step-joint-cpe-topology` 为准）。

---

## 跨步骤数据键（FlowContext）

`BUSINESS_DIAGNOSE_FLOW.config["shared_context_keys"]` 包括：

`business_outcome`、`causes_local`、`causes`、`joint_done`、`topology`、`cpe_result`、`targeted_probe`、`overlay_policy_flow`、`joint_needed`。

另有运行期键如 `cpe_ready`、`allow_probe_only`、`run_joint`、预置 `_cpe_collector` / `_topology_builder`（见 CLI 内 `business_diagnose` 函数）；新增键若需跨步骤依赖，仍须遵守「登记 / 合并语义」规则（`AI_SPEC_GUIDE`）。

---

## 证据与报告

| 能力 | 典型路径 |
|------|-----------|
| 本机业务 DNS/TCP/**Traceroute** 编排 | `business_diagnose.py` 内 `orchestrate_business_domain_port_diagnosis` 及对 `services/probe/business_host_probe.py`、`services/diagnosis/business_diagnosis.py` 的调用 |
| 本机业务 RCA | `services/diagnosis/business_rca_engine.py` 等 |
| 联合采集与拓扑、拓扑后根因 | `services/diagnosis/business_diagnose_followup.py` 及与 deep-dive 共用的 CPE/拓扑类型 |
| Overlay 证据链 | `services/diagnosis/overlay_policy_flow_evidence.py` |
| 报告 | `services/reporter/html_builder.py`、`reporting/templates/business_diagnosis.html`、`report_delivery_context.py` |

---

## 相关 spec / docs/rules

| 文档 | 用途 |
|------|------|
| [`spec/detail_function_design.md`](../../spec/detail_function_design.md) | 业务探测、联合诊断、退出码与报告章节 |
| [`docs/rules/product_features/`](../rules/product_features/) | 策略与转发口径 |
| [`.cursor/AI_SPEC_GUIDE.md`](../../.cursor/AI_SPEC_GUIDE.md) | 三条功能流自检、CLI 命名 |

---

## 单文件深描索引

优先阅读：`flow/definitions/business_diagnose.py`、`interface/cli/commands/business_diagnose.py`、`services/diagnosis/business_diagnose_followup.py`、`services/diagnosis/business_rca_engine.py`、`services/diagnosis/overlay_policy_flow_evidence.py`。

通过 [`SRC_INDEX.md`](SRC_INDEX.md) 打开对应 `docs/implementation/src/.../*.md` 深描（未建立则按镜像规范补齐）。
