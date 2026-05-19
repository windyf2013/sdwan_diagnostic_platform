"""业务探测未通过时：复用 CPE 采集、拓扑与 ``RootCauseEngine`` 的联合分析（与 deep-dive 证据链一致）。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.diagnosis import RootCause
from sdwan_desktop.services.analyzer.root_cause import RootCauseEngine
from sdwan_desktop.services.collector.cpe_collector import CpeCollector
from sdwan_desktop.services.diagnosis.business_diagnosis import BusinessDiagnosisOutcome
from sdwan_desktop.services.probe.planner import (
    extract_tunnel_peer_ips_from_cpe_configuration,
    plan_post_topology_probe_commands,
)
from sdwan_desktop.services.topology.topology import NetworkTopology
from sdwan_desktop.services.topology.topology_builder import TopologyBuilder
from sdwan_desktop.services.topology.pc_topology_input import snapshot_to_topology_input

logger = logging.getLogger(__name__)


def _extract_probe_target_ips(rows: List[Dict[str, Any]]) -> List[str]:
    """从业务探测行提取目标 IP（优先 TCP host，其次 DNS 解析结果）。"""
    ips: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tcp_rows = row.get("tcp") if isinstance(row.get("tcp"), list) else []
        for t in tcp_rows:
            if isinstance(t, dict) and t.get("host"):
                ips.append(str(t.get("host")))
        dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
        data = dns.get("data") if isinstance(dns.get("data"), dict) else {}
        for ip in data.get("resolved_ips") or []:
            ips.append(str(ip))
    dedup: List[str] = []
    seen = set()
    for ip in ips:
        if ip and ip not in seen:
            seen.add(ip)
            dedup.append(ip)
    return dedup


def business_probe_requires_joint_diagnosis(outcome: BusinessDiagnosisOutcome) -> bool:
    """业务 DNS/TCP 任一未达「可视为通达」时，需要 PC+CPE+拓扑联合结论。

    **注意**：每行 ``trace``（ICMP/UDP/TCP 路由追踪）仅作路径旁证；依据
    ``spec/detail_function_design.md`` §2.2.2，**不**因 traceroute 失败或「未到达目标」
    而单独触发本门控，以免与 TCP 服务路径或中间设备丢弃探测报文混淆。
    """
    if outcome.status == "partial" or bool(outcome.aggregate_error):
        return True
    for row in outcome.business_probes:
        dns = row.get("dns") or {}
        if dns.get("status") != "ok":
            return True
        for t in row.get("tcp") or []:
            if t.get("status") != "ok":
                return True
            data = t.get("data") or {}
            if data.get("port_open") is False:
                return True
    return False


async def run_joint_root_cause_after_business_probe(
    ctx: FlowContext,
    pc_snapshot: Any,
    business_outcome: BusinessDiagnosisOutcome,
    *,
    cpe_collector: CpeCollector,
    topology_builder: TopologyBuilder,
    cpe_mgmt_ip: str,
) -> Tuple[NetworkTopology, Any, Dict[str, Any], List[RootCause]]:
    """在已有 PC 快照与 ``business_probes`` 行上，执行 CPE 采集、拓扑后探测与根因引擎。

    不重跑 PC 侧 DNS/TCP，将首次探测结果并入 ``targeted_probe`` 信封供 ``RootCauseEngine`` 消费。
    """
    if not await cpe_collector.validate(ctx):
        raise RuntimeError("CPE 连接校验失败")

    cpe_result = await cpe_collector.collect(ctx)
    pc_data_dict = snapshot_to_topology_input(pc_snapshot)
    topology = topology_builder.build(pc_data_dict, cpe_result, cpe_mgmt_ip=str(cpe_mgmt_ip))

    data: Dict[str, Any] = {"business_probes": list(business_outcome.business_probes)}
    cpe_error: Optional[str] = None

    dt = "generic"
    if cpe_result and cpe_result.success and isinstance(cpe_result.data, dict):
        dt = cpe_result.data.get("device_type") or dt
        ctx.set("cpe_device_type", dt)
    data["device_type"] = dt

    biz_target_ips = _extract_probe_target_ips(list(business_outcome.business_probes))
    if biz_target_ips:
        data["biz_target_ips"] = biz_target_ips
    cfg = (
        cpe_result.data.get("cpe_configuration")
        if cpe_result and cpe_result.success and isinstance(cpe_result.data, dict)
        else None
    )
    tunnel_peer_ips = extract_tunnel_peer_ips_from_cpe_configuration(cfg)
    if tunnel_peer_ips:
        data["tunnel_peer_ips"] = tunnel_peer_ips
    cmds = plan_post_topology_probe_commands(
        str(dt),
        biz_target_ips=biz_target_ips,
        tunnel_peer_ips=tunnel_peer_ips or None,
        include_tunnel_peer_probes=False,
    )
    if cpe_result and cpe_result.success and cmds:
        try:
            pr = await cpe_collector.run_probe_commands(ctx, cmds)
            raw = dict((pr.data or {}).get("raw_outputs") or {})
            data["raw_outputs"] = raw
            if isinstance(pr.data, dict) and pr.data.get("device_type"):
                data["device_type"] = pr.data.get("device_type")
            if not pr.success:
                cpe_error = pr.error_message or "CPE 拓扑后探测失败"
        except Exception as exc:
            logger.warning("CPE 拓扑后探测异常: %s", exc, exc_info=True)
            cpe_error = str(exc)
            data.setdefault("raw_outputs", {})
    elif cpe_result and cpe_result.success and not cmds:
        data["reason"] = "no_probe_for_device_type"
        data.setdefault("raw_outputs", {})

    err_parts = [x for x in (cpe_error, business_outcome.aggregate_error) if x]
    envelope_error = "; ".join(err_parts) if err_parts else None
    status = "partial" if envelope_error else "ok"
    targeted_probe = {"status": status, "data": data, "error": envelope_error}

    engine = RootCauseEngine()
    causes = engine.analyze(
        topology,
        cpe_result,
        pc_data_dict,
        targeted_probe=targeted_probe,
        trace_id=ctx.trace_id,
        pc_snapshot=pc_snapshot,
    )
    return topology, cpe_result, targeted_probe, causes
