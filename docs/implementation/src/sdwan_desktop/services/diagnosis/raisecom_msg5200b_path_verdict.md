# raisecom_msg5200b_path_verdict

**Role**: 聚合 L1/L3/L5 与策略源匹配 → `JointOverlayDatapathGate`。

**Rules**: `raisecom_msg5200b_business_joint_gate.md` §3.

**Order**: 无会话 → L1 双向 vxlan → L1 全 DIP 隧道 → D1 策略源 → L2+L3 → L5 跳表 → underlay。

**Removed**: `raisecom_d0_public_underlay_veto`.
