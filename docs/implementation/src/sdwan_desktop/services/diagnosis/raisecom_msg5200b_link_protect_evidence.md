# raisecom_msg5200b_link_protect_evidence

**产品契约**：`docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md` §11.9.4。

## 职责

- 解析 `show link-protect status` 保护组动作口与 up/down。
- 结合 `CpeConfiguration.interfaces` / `show interface` 判断 vxlan/ge1 oper。
- 写入 `UrlGroupAnalysis.link_protect_summary` 与策略链 `overlay_iface` 步。

## 测试

- `tests/unit/services/diagnosis/test_raisecom_msg5200b_link_protect_reachability.py`
