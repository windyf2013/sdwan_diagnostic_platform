# html_builder

- **对应源码**: `src/sdwan_desktop/services/reporter/html_builder.py`
- **最近更新**: 2026-05-19 — 联合模板 `deep_dive_joint_ux.html` 精简首屏/交付摘要，证据链迁至 `partials/joint_evidence_chain.html`（补 L5/S1/S2、link-protect、mangle 节选等）。
- **2026-05-15** — `build_deep_dive_report`：当 `topology_data` 含 `report_html_h1`（联合业务等）时选用 `deep_dive_joint_ux.html`，否则沿用 `deep_dive.html`，便于验收期双模板并存。

## 深度诊断模板选用规则

| 条件 | 模板 |
|------|------|
| `topology_data.get("report_html_h1")` 为真 | `reporting/templates/deep_dive_joint_ux.html` |
| 否则 | `reporting/templates/deep_dive.html` |

联合 CLI 在 `business_diagnose._write_joint_deep_dive_style_report` 中写入 `report_html_h1` / `report_html_h1_note` 等拓扑展示键；纯 `sdwan-deep-dive` 无该键则走原版模板。

## 联合报告证据呈现

| 区块 | 模板 |
|------|------|
| 页首路径结论 | `deep_dive_joint_ux.html` → `report-joint-path-line`（`declared_business_datapath_banner` / `joint_path_evidence.datapath_banner_short`） |
| 证据链明细 | `partials/joint_evidence_chain.html`（L1/L3/L5、可达性、声明路径、策略链节选、原始采集） |
| 拓扑表 | `partials/topology_detail_tables.html`（联合场景默认折叠链路/节点表） |
