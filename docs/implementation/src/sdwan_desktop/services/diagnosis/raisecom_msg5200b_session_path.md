# raisecom_msg5200b_session_path

**Role**: L1 nf_conntrack 双向五元组旁证（5200B-only）。

**Rules**: `docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md` §2.1.

**Key API**: `evaluate_session_path_evidence`, `parse_conntrack_line_bidirectional`.

**Invariant**: 回程 `reply.src` 必须等于正向 `forward.dst`，避免同一行多条单向会话误判。
