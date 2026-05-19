# business_diagnose（CLI）

- **对应源码**: `src/sdwan_desktop/interface/cli/commands/business_diagnose.py`
- **最近更新**: 2026-05-16 — `finalize_business_topology_joint_report`：本机 `business_failure_stage.stage==ok` 时不将末跳→公网域标为故障；`_annotate_problem_nodes`：`failure_stage=server_port` 时不再向 cpe↔gw / gw↔hub 物理边写入 BIZ-TCP 故障标记（避免链路与应用层结论串线）。新增 ``_reconcile_joint_datapath_reading_layer``：当 ``topology_joint_presentation`` 隐藏 Overlay 而 ``compute_joint_overlay_datapath_gate`` 仍允许画隧道时，覆写 `declared_business_datapath_banner` 等与模板一致；``build_commercial_delivery_payload`` 使用 ``effective_underlay_declared_focus`` 与剖面对齐，并在该聚焦为真时跳过注入 ``overlay_policy_flow``。
- **关联规范**: [`spec/detail_function_design.md`](../../../../../../../spec/detail_function_design.md) §2.2.3；[`.cursor/AI_SPEC_GUIDE.md`](../../../../../../../.cursor/AI_SPEC_GUIDE.md) 三条功能流自检。

## 职责概述

Interface：`sdwan-business-diagnose` / `agentctl business-diagnose`；内联 `FlowRuntime` handlers。

## 对外接口

- 新增 `--no-traceroute`：关闭本机路由追踪。
- `step_biz_probe` 调用 `orchestrate_business_domain_port_diagnosis(..., enable_traceroute=not no_traceroute)`。

## 非 Python 资产

- 模板：`src/sdwan_desktop/reporting/templates/business_diagnosis.html`、`deep_dive.html` 中业务探测表增加 Traceroute 列/折叠跳明细。

## 测试

- `tests/unit/interface/test_business_diagnose_cli.py`。
