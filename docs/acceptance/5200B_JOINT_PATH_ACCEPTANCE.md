# Raisecom 5200B 联合业务路径 — 验收（Phase E）

> 契约：`docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md` §11  
> P0：**禁止**仅用子集 `pytest` 或仿真矩阵即宣称 Phase E 完成（见 `.cursor/rules/sdwan-p0-core.md` DoD §4）。

## 1. 自动化验收（必跑，通过才可写「自动化 OK」）

在仓库根目录执行：

```bash
python scripts/verify_5200b_path_phase_e.py
```

脚本覆盖（与 agentctl 真实路径对齐）：

| 类别 | 内容 |
|------|------|
| **test_map 触区** | `interface/cli` + `services/diagnosis` 相关用例 |
| **CLI joint_done** | 联合完成后 JSON/HTML 收尾（含 `_joint_overlay_gate_from_cli_context`） |
| **path_matrix** | 四类声明路径 fixture 契约 |
| **仿真矩阵** | 全场景 HTML + 门控 + path_matrix 列 |
| **implementation 镜像** | Phase E 新增/变更的 4 个 diagnosis 模块 |

退出码 **0** → 自动化通过；**非 0** → 不得声称 Phase E 验收完成。

首行汇报（Agent/CI）：`pytest: N passed, M failed`（脚本输出末行含统计）。

## 2. 仿真目视（自动化通过后建议）

```bash
python scripts/generate_joint_report_matrix.py
```

打开 `reports/sim_matrix/index.html`，核对 path_matrix 场景 **路径对账** 列与 HTML 中「url-group 与声明业务路径分析」块。

## 3. 实机验收（人工，脚本不代替）

| # | 场景 | 仿真 ID |
|---|------|---------|
| 1 | 纯互联网（域未入 url-group） | `12_path_internet_intent` |
| 2 | security-ip 未命中 | `13_path_security_miss` |
| 3 | link-protect / vxlan down | `14_path_link_protect_down` |
| 4 | 无 conntrack 采样（S1） | `15_path_s1_no_ct_sampling` |

命令示例：`agentctl business-diagnose -b <域> --cpe-host ...`（联合 CPE + 拓扑后探测）。

**人工验收:** 待办（填下表后改为「通过」）

| 日期 | 操作人 | 站点/CPE | 声明域 | 结果 | 报告路径 |
|------|--------|----------|--------|------|----------|
|      |        |          |        |      |          |

## 4. 曾漏验根因（Process）

| 问题 | 原因 | 对策 |
|------|------|------|
| `NameError: compute_joint_overlay_datapath_gate` | Phase E 瘦身删 import，但 joint_done 收尾仍调用；单测未覆盖 joint_done | `tests/acceptance/test_phase_e_5200b_path_gate.py` + 本脚本 |
| 宣称 Phase E 完成 | 只跑 `tests/unit/services/diagnosis/` 子集 | 必须跑 `verify_5200b_path_phase_e.py` |
