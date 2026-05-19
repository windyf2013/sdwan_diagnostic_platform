# 产品特性库（Product Feature Rules）

本库文档描述**具体产品/系列上的网络行为与诊断口径**，供实现 `overlay_policy_flow_evidence`、`RootCauseEngine`、联合报告、`TopologyBuilder` 等模块时对照，**不替代** `spec/` 中的通用架构契约。

**与项目规则库区分**：三条流产品定位、business 报告 UX（跨厂商）见 [`../THREE_FLOWS_PRODUCT_POSITIONING.md`](../THREE_FLOWS_PRODUCT_POSITIONING.md)、[`../BUSINESS_DIAGNOSE_REPORT_UX.md`](../BUSINESS_DIAGNOSE_REPORT_UX.md)。

## 文档列表

| 文档 | 产品/范围 | 摘要 |
|------|-----------|------|
| [raisecom_msg5200b_network_analysis.md](raisecom_msg5200b_network_analysis.md) | Raisecom MSG5200B（5200B） | Overlay（vxlan + tunnel type vxlan）、fwmark + 多路由表策略分流、DNS→ipset→mangle→ip rule 命中链；underlay 组合形态与**禁止断言的封装线序** |
| [raisecom_msg5200b_business_joint_gate.md](raisecom_msg5200b_business_joint_gate.md) | **5200B-only** · business-diagnose | 路径证据 **L0–L5**（conntrack 双向五元组、FIB、策略面、跳表）；废除公网 DIP D0；**禁止**用于其他型号 |

## 与代码模块的映射（查阅指引）

| 若你正在修改… | 建议先读 |
|---------------|----------|
| `services/diagnosis/overlay_policy_flow_evidence.py` | 5200B 文档 §1–§3、§6 |
| `raisecom_msg5200b_session_path.py` / `raisecom_msg5200b_fib_evidence.py` / `raisecom_msg5200b_path_verdict.py` / `raisecom_msg5200b_business_gate.py` | **business_joint_gate.md**（L0–L5）；network_analysis §4–§5 |
| `services/analyzer/root_cause.py`（CPE-003/004、会话证据） | 5200B 文档 §3–§5；`planner.py` 中 PC↔CPE NAT 与 conntrack 说明 |
| `services/reporter/joint_commercial_delivery.py`、报告模板 | REPORT_UX.md；business_joint_gate.md；network_analysis §2、§5.3 |
| `services/reporter/topology_joint_presentation.py` | THREE_FLOWS §3；REPORT_UX §3；**只读** gate 字段，禁止写 5200B if |
| `services/probe/planner.py`（拓扑后探测命令） | 5200B 文档 §4；`templates/whole_config_5200b.txt` |
| `services/parser/vendor/raisecom_msg5200b.py` | `spec/detail_function_design.md` 中解析章节 + 本文 5200B 行为 |
| `interface/cli/commands/business_diagnose.py` | THREE_FLOWS；FLOW_business_diagnose.md；business_joint_gate.md |

新增其他厂商/系列时，在本表增加一行，并在仓库根 `docs/rules/INDEX.md` 中同步；若含 business 联合门控，须单独 **{vendor}_business_joint_gate.md** 并标 **{型号}-only**。
