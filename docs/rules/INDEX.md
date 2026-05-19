# 规则文档索引（Rule Docs Index）

本目录存放**与代码内一键体检规则（`src/sdwan_desktop/services/analyzer/rules/*.py`）互补**的说明性规则：产品行为、网络功能分析约定、报告与证据链口径等。实现或修改**网络功能分析、联合诊断、Overlay/策略、根因与报告**前，请先按下方索引打开对应文档。

| 库 | 路径 | 适用场景 |
|----|------|----------|
| **三条流产品定位（项目核心理念）** | [`THREE_FLOWS_PRODUCT_POSITIONING.md`](THREE_FLOWS_PRODUCT_POSITIONING.md) | quick-check / deep-dive / business-diagnose 分工、分层 Underlay/Overlay、精确定位 vs 启发式 |
| **business-diagnose 报告 UX** | [`BUSINESS_DIAGNOSE_REPORT_UX.md`](BUSINESS_DIAGNOSE_REPORT_UX.md) | 联合 HTML：证据完整、结论简洁（尤其页首/交付/路径实证） |
| **产品特性库** | [`product_features/INDEX.md`](product_features/INDEX.md) | 厂商/型号相关的转发、隧道、策略分流、NAT 与现网行为抽象；避免与一键体检 Python 规则混淆 |
| **一键体检规则（代码）** | `src/sdwan_desktop/services/analyzer/rules/` | GW/DNS/SYSTEM/CONNECTIVITY 等可执行规则条目，见该包 `__init__.py` 头注释 |
| **瀑布/专项修复记录** | `docs/WATERFALL_*.md` 等 | 历史缺陷与 UI 行为修复，按需检索文件名 |
| **源码功能实现文档（镜像）** | [`docs/implementation/README.md`](../implementation/README.md)、[`spec/00_core/implementation_doc_mirror.md`](../../spec/00_core/implementation_doc_mirror.md) | 每份 `src/**/*.py` 对应 `docs/implementation/src/**/*.md`；改代码须同步更新，见 `.cursor/AI_SPEC_GUIDE.md` 核心约束第 8 条 |
| **实现层流程地图与全树索引** | [FLOW_quick_check.md](../implementation/FLOW_quick_check.md) 等、[SRC_INDEX.md](../implementation/SRC_INDEX.md)（生成） | Agent 先读 FLOW 再查 SRC_INDEX；索引由 `scripts/generate_implementation_index.py` 维护，`pre-commit` `--check` |

## 开发网络功能分析模块时的阅读顺序（建议）

0. **三条流 / 报告 UX**（改 business-diagnose 或联合 HTML 时 **必先**）→ [`THREE_FLOWS_PRODUCT_POSITIONING.md`](THREE_FLOWS_PRODUCT_POSITIONING.md)、[`BUSINESS_DIAGNOSE_REPORT_UX.md`](BUSINESS_DIAGNOSE_REPORT_UX.md)。
1. **本索引** → 确认任务属于「项目核心理念」「产品特性」还是「通用体检规则」。
2. **产品特性库** [`product_features/INDEX.md`](product_features/INDEX.md) → 打开具体厂商/系列文档；5200B 联合门控见 [`raisecom_msg5200b_business_joint_gate.md`](product_features/raisecom_msg5200b_business_joint_gate.md)（**5200B-only**）。
3. **项目规范** → `.cursor/AI_SPEC_GUIDE.md` 中「文档查阅协议」与「日志与代码注释」基础规则。
4. **详细设计** → `spec/detail_function_design.md`（解析器、探测、CLI 等章节）。
5. **实现层导航** → 先按需读 `docs/implementation/FLOW_*.md` 与 [`SRC_INDEX.md`](../implementation/SRC_INDEX.md)，再按 `spec/00_core/implementation_doc_mirror.md` 更新或新建 `docs/implementation/src/...` 下同路径 `.md`。

维护约定：新增产品系列文档时，**必须**在 `product_features/INDEX.md` 增加条目，并在本文件上表增加一行（或合并说明）。
