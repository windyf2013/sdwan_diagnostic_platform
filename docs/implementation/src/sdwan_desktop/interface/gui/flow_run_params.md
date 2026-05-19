# flow_run_params

- **对应源码**: `src/sdwan_desktop/interface/gui/flow_run_params.py`
- **关联规范**: `.cursor/AI_SPEC_GUIDE.md` §边界 pydantic；`FLOW_deep_dive.md` / `FLOW_business_diagnose.md`

## 职责概述

深度诊断与业务路径诊断 GUI 入口参数的 pydantic 校验与 `agentctl` argv 拼装；避免未校验 dict 进入子进程 CLI。
