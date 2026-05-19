# topology_joint_presentation



- **对应源码**: `src/sdwan_desktop/services/reporter/topology_joint_presentation.py`

- **最近更新**: 2026-05-16 — `path_focus_beyond_sdwan`（抑制 CPE 启发式标红）与 `underlay_fault_on_internet_ingress`（公网 ingress 故障示意）分离：`business_probe_all_ok` 时后者为假且叙述不含「故障段示意」。连接符 tooltip 与 `report_joint_nf_conntrack_had_session_lines` 对齐（见模板 `_bj_has_ct`）。

- **关联规范**: [`spec/detail_function_design.md`](../../../../../../spec/detail_function_design.md) §2.2.2；[`FLOW_business_diagnose.md`](../../../../FLOW_business_diagnose.md)。



## 职责概述



联合业务报告 HTML 中 **Underlay / Overlay 剖面** 的单一决策入口（`resolve_joint_topology_presentation`），供 `business_diagnose.finalize_business_topology_joint_report` 与 `_annotate_problem_nodes` 共用。



## 关键不变量



1. **是否画 Overlay 条带**：唯一权威为 `compute_joint_overlay_datapath_gate` → `show_overlay_tunnel_strip`。

2. **是否进入 sdwan 变体**：与 `show_overlay_tunnel_strip` 同真；`egress_past_cpe` 仅驱动 `path_focus_beyond_sdwan`（公网域），不触发 Overlay。

3. **核查通过 vs 故障叙事**：`business_probe_all_ok=True` 时 `underlay_fault_on_internet_ingress=False`，`narrative_coherence_note` 使用「本机探测已通过」表述，链路一览 tunnel 行由模板 `business_probe_all_ok` 控制。



## 测试



- `tests/unit/services/reporter/test_topology_joint_presentation.py`


