# report_text_sanitize

- **对应源码**: `src/sdwan_desktop/services/reporter/report_text_sanitize.py`
- **最近更新**: 2026-05-15 — 结论/根因/探测错误文案去除 `(trace_id: …)`。
- **关联规范**: 无；用户可见层与 JSON 内 `trace_id` 字段分离。

## 职责概述

`sanitize_user_visible_text`、`sanitize_root_causes_for_display`：HTML 结论区不重复调试 ID。
