# html_builder

- **对应源码**: `src/sdwan_desktop/services/reporter/html_builder.py`
- **最近更新**: 2026-05-15 — `build_deep_dive_report`：当 `topology_data` 含 `report_html_h1`（联合业务等）时选用 `deep_dive_joint_ux.html`，否则沿用 `deep_dive.html`，便于验收期双模板并存。

## 深度诊断模板选用规则

| 条件 | 模板 |
|------|------|
| `topology_data.get("report_html_h1")` 为真 | `reporting/templates/deep_dive_joint_ux.html` |
| 否则 | `reporting/templates/deep_dive.html` |

联合 CLI 在 `business_diagnose._write_joint_deep_dive_style_report` 中写入 `report_html_h1` / `report_html_h1_note` 等拓扑展示键；纯 `sdwan-deep-dive` 无该键则走原版模板。
