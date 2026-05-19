# business_host_probe

- **对应源码**: `src/sdwan_desktop/services/probe/business_host_probe.py`
- **最近更新**: 2026-05-18 — 多个 `BizDomainPortSpec` 之间 **`asyncio.gather` 并行**（单域名内 DNS→TCP→traceroute 仍顺序）；2026-05-15 — 每域名仅对首个 IPv4 A 记录执行一次 traceroute（多 A 时 TCP 仍逐地址）；默认 `tcp_count=1`、`traceroute_max_hops=12`；traceroute 失败不进入 `aggregate_error`。
- **关联规范**: [`spec/detail_function_design.md`](../../../../../../spec/detail_function_design.md) §2.2.2；[`FLOW_business_diagnose.md`](../../../../FLOW_business_diagnose.md)。

## 职责概述

Service 层：在 PC 侧对声明的 `FQDN:端口` 执行 **DNS(A)**、对至多 `max_addrs_per_domain` 个 IPv4 的 **tcping**，并在默认开启时对**首个**解析 IPv4 执行一次 **traceroute**（路径旁证，经 `ToolDispatcher`）。**多个域名**之间并发调度，返回行顺序与输入 `targets` 一致。

## 对外接口

- `parse_biz_target_tokens` / `BizDomainPortSpec`：CLI 目标解析。
- `run_business_domain_port_probes(...)`：异步探测主入口；多域名 `asyncio.gather` 并行；`enable_traceroute=False` 时 `trace` 恒为空列表；`aggregate_error` **仅**聚合 DNS/TCP 关键失败。

## 关键行为与不变量

- **门控分离**：不把 traceroute 结果并入 `err_parts`，避免与 `business_probe_requires_joint_diagnosis` 冲突（ICMP 与 TCP 路径可能不一致）。
- **数据形状**：每行 `trace[]` 元素含 `host`、`port`（业务 TCP 端口）、`status`、`data.summary` / `data.hops`、`error`。

## 依赖与测试

- 依赖：`ToolDispatcher`、`ToolRequest`/`ToolResponse`、`FlowContext.trace_id`。
- 测试：`tests/unit/services/probe/test_business_host_probe.py`。
