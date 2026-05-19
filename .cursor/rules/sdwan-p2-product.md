---
description: P2 产品级 — 联合报告 UX、5200B 门控、Overlay/策略与报告呈现口径
globs: src/sdwan_desktop/services/diagnosis/**,src/sdwan_desktop/services/reporter/**,src/sdwan_desktop/reporting/**,src/sdwan_desktop/services/analyzer/**
alwaysApply: false
---

# P2 产品级（glob 自动挂载）

入口：`docs/rules/INDEX.md`。

| 场景 | 必读 |
|------|------|
| business-diagnose / 联合 HTML | `THREE_FLOWS_PRODUCT_POSITIONING.md`、`BUSINESS_DIAGNOSE_REPORT_UX.md` |
| 5200B 门控 | `product_features/raisecom_msg5200b_business_joint_gate.md`（5200B-only） |
| 5200B 转发/NAT | `product_features/raisecom_msg5200b_network_analysis.md` |
| 一键体检规则 | `src/.../analyzer/rules/` |

禁止在 presentation/delivery 层写 5200B 专有 if。
