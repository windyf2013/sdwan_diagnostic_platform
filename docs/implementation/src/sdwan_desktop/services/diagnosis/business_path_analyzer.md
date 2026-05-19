# business_path_analyzer

- **对应源码**: `src/sdwan_desktop/services/diagnosis/business_path_analyzer.py`
- **最近更新**: 2026-05-15 — TCP 类根因描述可附加 ICMP traceroute **旁证**句（`_icmp_trace_path_hint_for_row`）。
- **关联规范**: [`spec/detail_function_design.md`](../../../../../../spec/detail_function_design.md) §2.2.2。

## 职责概述

从 `business_probes` 行生成 BIZ-* 根因（负面结论为主）。

## 关键行为

- `trace` 不单独生成新 `BIZ-TRACE-*` ID；仅在 TCP 已失败时增强描述，避免与 TCP 通达结论冲突。

## 测试

- `tests/unit/services/diagnosis/test_business_path_analyzer.py`。
