# deep_dive（CLI）

- **对应源码**: `src/sdwan_desktop/interface/cli/commands/deep_dive.py`
- **最近更新**: 2026-05-15 — 注册 `traceroute`；`--no-traceroute`；`step_targeted_probe` 内业务探测透传 `enable_traceroute`。
- **关联规范**: [`spec/detail_function_design.md`](../../../../../../../spec/detail_function_design.md) §2.2.4。

## 职责概述

深度诊断主 CLI；拓扑后可选 PC 侧业务探测，与 CPE 命令输出合并为 `targeted_probe` 信封。

## 关键行为

- 与 `business-diagnose` 共用 `orchestrate_business_domain_port_diagnosis` 参数语义。
