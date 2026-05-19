# joint_overlay_datapath_gate

- **对应源码**: `src/sdwan_desktop/services/diagnosis/joint_overlay_datapath_gate.py`
- **最近更新**: 2026-05-16 — 跨厂商分发入口；`JointOverlayDatapathGate` 含 `evidence_tier` / `show_business_flow_overlay`。
- **关联规范**: `docs/rules/THREE_FLOWS_PRODUCT_POSITIONING.md`；`docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`。

## 职责概述

`compute_joint_overlay_datapath_gate` 按 `is_raisecom_msg5200b_cpe` 分发至 `raisecom_msg5200b_business_gate` 或 `generic_joint_overlay_gate`。

## 测试

- `tests/unit/services/diagnosis/test_raisecom_msg5200b_session.py`
- `tests/unit/services/diagnosis/test_generic_joint_overlay_gate.py`
