# agentctl_worker

- **对应源码**: `src/sdwan_desktop/interface/gui/agentctl_worker.py`
- **关联**: `cli_runner.py`（开发子进程 / 打包进程内 Click）

## 职责概述

`AgentctlWorker`：GUI 后台线程执行 `deep-dive` / `business-diagnose` 等子命令；开发环境 `subprocess.Popen` 支持 `cancel()` 终止。
