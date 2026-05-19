# business_diagnosis

- **对应源码**: `src/sdwan_desktop/services/diagnosis/business_diagnosis.py`
- **最近更新**: 2026-05-15 — 编排默认与 `business_host_probe` 模块常量对齐（`tcp_count=1`、traceroute 12 跳 × 2s）；避免编排层与探针层默认漂移。
- **关联规范**: [`spec/detail_function_design.md`](../../../../../../spec/detail_function_design.md) §2.2.2。

## 职责概述

编排「仅探测」阶段，返回 `BusinessDiagnosisOutcome`（无根因列表）。

## 对外接口

- `orchestrate_business_domain_port_diagnosis(...)`：默认取自 `business_host_probe.DEFAULT_*`；与 CLI `--no-traceroute` 对齐。

## 测试

- `tests/unit/services/diagnosis/test_business_diagnosis_orchestrator.py`。
