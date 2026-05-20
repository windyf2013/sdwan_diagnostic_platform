# raisecom_msg5200b_url_group

**产品契约**：`docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md` §11；`raisecom_msg5200b_network_analysis.md` §4.1。

## 职责

- 解析 `show url-group all domain all` 与 running-config `url match fuzzy|precise|suffix`。
- `domain_matches_url_group_entry()`：三组模式见 `raisecom_msg5200b_network_analysis.md` §4.1。
- `evaluate_url_group_priority_for_domain()` / `build_raisecom_msg5200b_url_group_analysis()`。

## 测试

- `tests/unit/services/diagnosis/test_raisecom_msg5200b_url_group.py`
