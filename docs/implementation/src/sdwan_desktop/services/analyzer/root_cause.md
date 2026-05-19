# root_cause

- **对应源码**: `src/sdwan_desktop/services/analyzer/root_cause.py`
- **最近更新**: 2026-05-15 — `_targeted_business_probes_all_ok` docstring 明确忽略 `trace`（与 `targeted_probe_business_rows_all_ok` 一致）。
- **关联规范**: [`spec/detail_function_design.md`](../../../../../../spec/detail_function_design.md) §2.2.2。

## 职责概述

`RootCauseEngine`：拓扑与 CPE 证据上的根因归纳；业务探测「全部通达」调和逻辑仍以 DNS+TCP 为准。
