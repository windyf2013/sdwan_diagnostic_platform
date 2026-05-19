# business_diagnose_followup

- **对应源码**: `src/sdwan_desktop/services/diagnosis/business_diagnose_followup.py`
- **最近更新**: 2026-05-15 — `business_probe_requires_joint_diagnosis` docstring 明确 **不含**仅 traceroute 异常。
- **关联规范**: [`spec/detail_function_design.md`](../../../../../../spec/detail_function_design.md) §2.2.3。

## 职责概述

业务探测未通过时的 CPE+拓扑联合与 `targeted_probe` 信封组装。

## 关键行为

- 联合门控仍仅基于 **DNS + TCP**（及 `aggregate_error` / `partial` 等既有语义）。
