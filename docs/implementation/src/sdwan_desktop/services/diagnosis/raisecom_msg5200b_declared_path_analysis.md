# raisecom_msg5200b_declared_path_analysis

**Role**: 5200B 联合 business-diagnose 路径分析门面（`analyze_raisecom_msg5200b_declared_business_path`）。

**Output**: `DeclaredBusinessPathAnalysis` → `topology.declared_business_path_analysis`、嵌入 `joint_path_evidence`。

**Deps**: `raisecom_msg5200b_url_group`、`raisecom_msg5200b_policy_chain_contrast`；门控仍由 `path_verdict` 产出后只读映射。
