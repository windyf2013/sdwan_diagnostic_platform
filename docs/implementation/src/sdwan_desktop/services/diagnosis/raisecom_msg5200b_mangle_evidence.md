# raisecom_msg5200b_mangle_evidence

**产品契约**：`docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md` §2.2、§11.5。

## 职责

- 解析 `diagnose:iptables -t mangle -nvL` 的 **PREROUTING** 链 `MARK set 0xNN` 行及 pkts 计数。
- 从 `diagnose:ip rule show` 节选 `fwmark → lookup` 行。
- `evaluate_mangle_evidence()` 供 `raisecom_msg5200b_policy_chain_contrast.py` 写入 `mangle` / `ip_rule` 步。

## 调用方

- `raisecom_msg5200b_policy_chain_contrast.build_raisecom_msg5200b_policy_chain_and_reconcile`

## 测试

- `tests/unit/services/diagnosis/test_raisecom_msg5200b_mangle_evidence.py`
