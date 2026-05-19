# deep_dive_joint_ux.html

- **对应文件**: `src/sdwan_desktop/reporting/templates/deep_dive_joint_ux.html`
- **最近更新**: 2026-05-15 — 从 `deep_dive.html` 派生的联合业务专用模板；验收通过前与原版并存，勿删 `deep_dive.html`。

## 选用条件

由 `HtmlReportBuilder.build_deep_dive_report` 在 `topology` 字典含 `report_html_h1` 时加载（见 [`html_builder.md`](../services/reporter/html_builder.md)）。

## 与 `deep_dive.html` 的差异要点

- Hero：先「探测现象 / 主故障判断 / 已排除」，再「主叙述」辅文；「待核对」置于 `<details>` 默认折叠。
- 页眉副标题 class `report-header-subline`；交付摘要 headline/subline 使用 `delivery-headline` / `delivery-subline` 统一字号阶梯。
- 页眉 **不展示** `report_html_h1_note`（如「本机业务探测未通过；已叠加 PC 快照…」）；探测结论在下方 hero 区。
- 页眉 meta 保留：业务目标（若有）、报告 ID、Trace ID、生成时间、**诊断类型**、**规则版本**；正文类值用 `meta-value--prose`，UUID/版本号用 `meta-value--mono`。
- 各 `section` 仍为 `collapsible collapsed` + `hidden`（P1：默认全不展开，与原版一致）。
