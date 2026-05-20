# heuristic_cause_consolidation

- **对应源码**: `src/sdwan_desktop/services/analyzer/heuristic_cause_consolidation.py`
- **职责**: business-diagnose 联合场景将 CPE-003 / CPE-004 / CPE-002-WARN 等配置启发式合并为单条 `CPE-CONFIG-HEURISTIC`，禁止在根因卡片与页首待核对区堆叠多段【与…对齐】旁证。
- **调用方**: `RootCauseEngine.analyze` 收尾；`joint_report_probe_outcome._secondary_findings` 只展示一条配置待核对。
- **规范**: `docs/rules/BUSINESS_DIAGNOSE_REPORT_UX.md` §2.2（禁止页首多段启发式推导）
