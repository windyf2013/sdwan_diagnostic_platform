# business_rca_engine

- **对应源码**: `src/sdwan_desktop/services/diagnosis/business_rca_engine.py`
- **最近更新**: 2026-05-15 — `HypothesisGenerator` 在存在成功 `trace` 行时增加 **H-ICMP-TRACE** 假设。
- **关联规范**: [`spec/detail_function_design.md`](../../../../../../spec/detail_function_design.md) §2.2.2。

## 职责概述

融合 `ObservationContext` 与 `ProbeBundle`，输出带边界的业务根因与假设列表。

## 测试

- `tests/unit/services/diagnosis/test_business_rca_engine.py`。
