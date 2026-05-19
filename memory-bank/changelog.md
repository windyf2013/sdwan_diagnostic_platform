# 变更日志（冷存储，勿作 Agent 每轮闸门）

> 新条目写在顶部。`activeContext.md` 已退役为闸门，请只维护本文件与 `INDEX.md`。

## 2026-05-19 — 规则体系 v3.1

- B0/P0/P1/P2 + L1/L2；`.cursor/rules/sdwan-p0-core.md` 唯一 alwaysApply
- 三条流自检迁至 `.cursor/rules/P1-three-flows-shared.md`；`AI_SPEC_GUIDE` 索引化

## 2026-05-19 — 深度诊断 GUI 性能

- GUI 默认 `AgentctlWorker` 子进程；Flow 拆 `step-biz-probe` / `step-cpe-post-probe`（9 步）

## 2026-05-15 — 联合报告页首结论

- `joint_commercial_delivery` / `joint_report_probe_outcome` 单一主叙述；hero 两层结构

## 2026-05-13 — 三命令商用对齐

- `report_pack` 扉页；GUI 业务路径诊断页；quick/business JSON

## 2026-05-12 — CPE Telnet / 拓扑

- 5200B busybox `#` 提示符；拓扑 vxlan 本地侧解析；deep_dive 报告 PC 节点修复

## 2026-05-12 — Raisecom 5200B

- `raisecom_msg5200b` 指纹与解析器；Telnet EOF 快速失败

（更早 Sprint 8 打包与用户手册等见 git 历史 / `progress.md`）
