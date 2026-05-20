"""业务探测未通过时：复用 CPE 采集、拓扑与 ``RootCauseEngine`` 的联合分析（与 deep-dive 证据链一致）。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.core.types.diagnosis import RootCause
from sdwan_desktop.services.analyzer.root_cause import RootCauseEngine
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.collector.cpe_collector import CpeCollector
from sdwan_desktop.services.diagnosis.business_diagnosis import BusinessDiagnosisOutcome
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_conntrack_diff import (
    diff_evidence_to_dict,
    evaluate_conntrack_diff_evidence,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import is_raisecom_msg5200b_cpe
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


def _merge_probe_raw_outputs(
    cpe_result: Any,
    business_outcome: BusinessDiagnosisOutcome,
) -> Dict[str, str]:
    """从并行 CPE 采集结果合并 ``raw_outputs`` 供 ``targeted_probe`` 使用。"""
    raw: Dict[str, str] = {}
    if cpe_result and cpe_result.success and isinstance(cpe_result.data, dict):
        ro = cpe_result.data.get("raw_outputs")
        if isinstance(ro, dict):
            raw.update({str(k): str(v) for k, v in ro.items()})
    return raw


def _attach_conntrack_diff(
    data: Dict[str, Any],
    cpe_configuration: Any,
    pc_ip: Optional[str],
) -> None:
    if not is_raisecom_msg5200b_cpe(cpe_configuration):
        return
    diff_ev = evaluate_conntrack_diff_evidence(data, cpe_configuration, pc_ip)
    data["conntrack_diff"] = diff_evidence_to_dict(diff_ev)


async def run_joint_root_cause_after_business_probe(
    ctx: FlowContext,
    pc_snapshot: Any,
    business_outcome: BusinessDiagnosisOutcome,
    *,
    cpe_collector: CpeCollector,
    topology_builder: TopologyBuilder,
    cpe_mgmt_ip: str,
    cpe_result: Optional[CollectorResult] = None,
) -> Tuple[NetworkTopology, Any, Dict[str, Any], List[RootCause]]:
    """在已有 PC 快照与 ``business_probes`` 行上，执行 CPE 采集、拓扑后探测与根因引擎。

    若 ``cpe_result`` 已由并行 CPE Task 写入 ``ctx``，则不再 ``collect()``。
    """
    if cpe_result is None:
        cpe_result = ctx.get("cpe_result")

    if cpe_result is None:
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

    raw_merged = _merge_probe_raw_outputs(cpe_result, business_outcome)
    data["raw_outputs"] = raw_merged

    cfg = (
        cpe_result.data.get("cpe_configuration")
        if cpe_result and cpe_result.success and isinstance(cpe_result.data, dict)
        else None
    )
    tunnel_peer_ips = extract_tunnel_peer_ips_from_cpe_configuration(cfg)
    if tunnel_peer_ips:
        data["tunnel_peer_ips"] = tunnel_peer_ips

    skip_keys = set(raw_merged.keys())
    cmds = plan_post_topology_probe_commands(
        str(dt),
        biz_target_ips=biz_target_ips,
        tunnel_peer_ips=tunnel_peer_ips or None,
        include_tunnel_peer_probes=False,
        skip_keys=skip_keys,
    )
    if cpe_result and cpe_result.success and cmds:
        try:
            pr = await cpe_collector.run_probe_commands(ctx, cmds)
            raw_merged.update(dict((pr.data or {}).get("raw_outputs") or {}))
            data["raw_outputs"] = raw_merged
            if isinstance(pr.data, dict) and pr.data.get("device_type"):
                data["device_type"] = pr.data.get("device_type")
            if not pr.success:
                cpe_error = pr.error_message or "CPE 拓扑后探测失败"
        except Exception as exc:
            logger.warning("CPE 拓扑后探测异常: %s", exc, exc_info=True)
            cpe_error = str(exc)
    elif cpe_result and cpe_result.success and not raw_merged and not cmds:
        data["reason"] = "no_probe_for_device_type"

    if not cpe_result.success:
        cpe_error = cpe_result.error_message or "CPE 采集失败"

    pc_ip = None
    if isinstance(pc_data_dict, dict):
        pc_ip = pc_data_dict.get("primary_ip") or pc_data_dict.get("ip_address")
    _attach_conntrack_diff(data, cfg, pc_ip)

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
