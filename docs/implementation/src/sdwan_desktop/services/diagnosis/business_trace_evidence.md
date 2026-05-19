# business_trace_evidence

- **对应源码**: `src/sdwan_desktop/services/diagnosis/business_trace_evidence.py`
- **最近更新**: 2026-05-16 — 增加 `egress_shape`（`wan_gateway` / `early_public`）与 `compute_egress_shape`。
- **关联规范**: `spec/detail_function_design.md` §2.2.2；`docs/rules/product_features/raisecom_msg5200b_network_analysis.md` §5.2。

## 职责概述

从 `targeted_probe.data.business_probes[].trace` 提炼 `BusinessTraceEvidence`（如 `egress_past_cpe`），供：

- `compute_joint_overlay_datapath_gate`（展示 Overlay 隧道条）
- `failure_beyond_sdwan_edge_likely` / `_annotate_problem_nodes`（抑制 CPE 误标红）
- `RootCauseEngine._apply_trace_evidence`（BIZ-TCP 叙述）

## 测试

- `tests/unit/services/diagnosis/test_business_trace_evidence.py`
