# deep_dive_tab

- **对应源码**: `src/sdwan_desktop/interface/gui/tabs/deep_dive_tab.py`
- **最近更新**: 2026-05-19 — GUI 默认经 `AgentctlWorker` 子进程执行 `deep-dive`（与终端 CLI 同宿主）；`SDWAN_DEEP_DIVE_INPROCESS=1` 时回退 `DeepDiveWorker`。

## 职责概述

深度诊断 GUI：CPE 连接、凭证 YAML；默认三域 + traceroute（与 CLI 一致，**不提供** GUI「跳过 traceroute」）。`DeepDiveGuiRunParams.to_argv()` 不传 `--no-traceroute`。

## 执行路径

| 模式 | 触发 | 行为 |
|------|------|------|
| 默认 | 正常启动 | `AgentctlWorker` + `cli_runner.run_agentctl`，解析 `[n/9]` 进度 |
| 回退 | `SDWAN_DEEP_DIVE_INPROCESS=1` | `DeepDiveWorker` 进程内 `run_deep_dive_flow` |

## Flow 步骤（v1.2.0）

9 步：`step-biz-probe`（300s）+ `step-cpe-post-probe`（180s）替代原合并的 `step-targeted-probe`；`step-cpe-collect` 180s。

## 报告交付

完成时 `prompt_save_on_complete=False`，`defer_auto_open=True`（不阻塞诊断线程）。
