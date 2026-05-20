# raisecom_msg5200b_reachability_evidence

**产品契约**：`docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md` §11.7.1。

## 职责

- **S1** PC→CPE：conntrack 采样 vs 本机 DNS/TCP 结果分级。
- **S2** CPE→NH：FIB 下一跳 + `show arp` + 可选 `diagnose:ping*` 旁证。
- 输出 `DeclaredBusinessPathAnalysis.reachability`；S2 不可达时可设 `break_point=next_hop_unreachable`。

## 测试

- `tests/unit/services/diagnosis/test_raisecom_msg5200b_link_protect_reachability.py`
