# business_joint_runtime_coordinator

business-diagnose 联合模式：`Task_probe`（三阶段 DNS→TCP→trace）与 `Task_cpe`（单次建连：baseline conntrack → post/runtime → 全量 collect）并行。回调 **仅 notify**（`asyncio.Event.set`），禁止在 probe 路径 await CPE 命令。
