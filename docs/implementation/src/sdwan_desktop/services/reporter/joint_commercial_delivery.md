# joint_commercial_delivery

- **对应源码**: `src/sdwan_desktop/services/reporter/joint_commercial_delivery.py`
- **最近更新**: 2026-05-15 — 抽出公共 `build_joint_primary_narrative`，与页首 hero 结论区共享单一事实源。
- **关联规范**: [`spec/detail_function_design.md`](../../../../../../spec/detail_function_design.md) §2.2.2。

## 职责概述

联合报告商用阅读层载荷；`all_ok` 口径与根因引擎「业务通达」语义一致，仅 DNS+TCP。

## 主叙述单一事实源（重要）

- 公共函数 `build_joint_primary_narrative(*, tunnel_rows, conntrack_lines, has_syn_only, cause_ids, biz_all_ok=False, underlay_declared_business_focus=False) -> (headline, sub_bullets)` 为联合报告**唯一**的主叙述选择器。
- 决策顺序（与商用交付 `headline` 一致）：
  1. `biz_all_ok=True` → 「本机已通 / 可达性基线」叙述；
  2. 任一隧道 peer ICMP 失败 → 「Underlay/隧道存疑」叙述（业务 TCP 超时按连带现象处理）；
  3. 全部隧道 peer ICMP 通 + conntrack 命中 + SYN-only → 「对端以远」叙述（非「隧道完全不通」）；
  4. conntrack 命中=0 → 「未观察到声明流」叙述；
  5. 兜底「按核查表与根因卡片对账」。
- `_pick_primary_narrative` 保留为历史别名，新代码请直接使用 `build_joint_primary_narrative`。
- 页首 hero 区 ([`joint_report_probe_outcome`](joint_report_probe_outcome.md)) 与 `_write_joint_deep_dive_style_report` 交付摘要均调用本函数，字符串级一致，避免「页首一种说法、摘要另一种说法」的口径漂移。
