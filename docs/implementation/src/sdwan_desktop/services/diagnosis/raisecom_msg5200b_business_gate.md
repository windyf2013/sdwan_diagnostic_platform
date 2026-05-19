# raisecom_msg5200b_business_gate

- **对应源码**: `src/sdwan_desktop/services/diagnosis/raisecom_msg5200b_business_gate.py`
- **最近更新**: 2026-05-16 — 5200B-only D0–D4 门控；D5 url-group 补充经 `raisecom_msg5200b_url_group`。
- **关联规范**: `docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md`。

## 职责概述

实现 `compute_raisecom_msg5200b_joint_overlay_gate`：D0 全公网 DIP 硬否决、D1 策略源、D2 全隧道 DIP、D3 跳表启发式、D4 Underlay-only。

## 测试

- `tests/unit/services/diagnosis/test_raisecom_msg5200b_session.py`
