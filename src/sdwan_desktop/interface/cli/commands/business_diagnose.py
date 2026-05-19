"""
本机业务不通诊断 CLI：PC 侧域名 + TCP 端口 + 可选 ICMP 路径追踪；探测未通过时须继续 CPE/拓扑联合分析
（与 deep-dive 证据链一致）。路径追踪结论不单独驱动「须联合」门控，见 ``business_probe_requires_joint_diagnosis``。
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

import click

import sdwan_desktop.tools.implementations.network.dns  # noqa: F401 register dns tool
import sdwan_desktop.tools.implementations.network.tcping  # noqa: F401 register tcping tool
import sdwan_desktop.tools.implementations.network.traceroute  # noqa: F401 register traceroute tool

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.flow.definitions.business_diagnose import BUSINESS_DIAGNOSE_FLOW
from sdwan_desktop.runtime.engine import FlowRuntime
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity
from sdwan_desktop.core.types.business_rca import ProbeBundle
from sdwan_desktop.services.collector.cpe_collector import CpeCollector, CpeCollectorConfig
from sdwan_desktop.services.collector.cpe_credentials_loader import (
    default_cpe_credentials_path,
    load_device_credentials_file,
)
from sdwan_desktop.services.collector.cpe_view_credentials_loader import (
    default_cpe_view_credentials_path,
    load_view_credentials_file,
)
from sdwan_desktop.services.collector.windows_collector import WindowsCollector
# 联合分析须向 run_joint_root_cause_after_business_probe 注入 TopologyBuilder 实例；
# 职责与 deep_dive CLI 中 topology_builder = TopologyBuilder() 一致，非重复实现。
from sdwan_desktop.services.topology.topology_builder import TopologyBuilder
from sdwan_desktop.services.diagnosis.business_diagnose_followup import (
    business_probe_requires_joint_diagnosis,
    run_joint_root_cause_after_business_probe,
)
from sdwan_desktop.services.diagnosis.declared_business_datapath import (
    targeted_probe_has_business_target_conntrack_hits,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    JointOverlayDatapathGate,
    compute_joint_overlay_datapath_gate,
)
from sdwan_desktop.services.diagnosis.business_diagnosis import (
    BusinessDiagnosisOutcome,
    orchestrate_business_domain_port_diagnosis,
)
from sdwan_desktop.services.diagnosis.business_rca_engine import (
    BusinessRCAEngine,
    build_observation_standalone,
)
from sdwan_desktop.services.probe.business_host_probe import (
    BizDomainPortSpec,
    parse_biz_target_tokens,
)
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder
from sdwan_desktop.services.reporter.joint_commercial_delivery import (
    build_commercial_delivery_payload,
    business_joint_should_present_overlay_tunnel_narrative,
    failure_beyond_sdwan_edge_likely,
    joint_datapath_evidence_from_targeted_probe,
    path_beyond_tunnel_likely,
    targeted_probe_business_rows_all_ok,
)
from sdwan_desktop.services.reporter.topology_joint_presentation import (
    JointTopologyPresentation,
    resolve_joint_topology_presentation,
)
from sdwan_desktop.services.reporter.joint_report_probe_outcome import (
    build_joint_report_probe_outcome,
)
from sdwan_desktop.services.diagnosis.business_trace_evidence import (
    analyze_business_trace_evidence,
)
from sdwan_desktop.services.reporter.report_text_sanitize import (
    sanitize_root_causes_for_display,
    sanitize_user_visible_text,
)
from sdwan_desktop.services.reporter.report_delivery_context import (
    build_business_diagnose_pack,
    biz_targets_from_business_probes,
    biz_targets_from_targeted_probe,
)
from sdwan_desktop.services.diagnosis.overlay_policy_flow_evidence import (
    run_overlay_policy_flow_step,
)

logger = logging.getLogger(__name__)

# 未证实声明业务经 Overlay/隧道面时，不得用隧道库存类根因冒充「该流路径结论」。
# Overlay 证据门控见 ``compute_joint_overlay_datapath_gate``（5200B 会话规则 + 非 5200B 回退）。
_TUNNEL_INVENTORY_CAUSE_IDS = frozenset({"CPE-002", "CPE-002-WARN"})


def _joint_overlay_gate_from_cli_context(
    targeted_probe: Optional[dict],
    cpe_result: Any,
    topology: Any,
) -> JointOverlayDatapathGate:
    cpe_cfg = None
    if cpe_result and getattr(cpe_result, "success", False) and isinstance(cpe_result.data, dict):
        cpe_cfg = cpe_result.data.get("cpe_configuration")
    top_d = topology.to_dict() if topology is not None and hasattr(topology, "to_dict") else None
    return compute_joint_overlay_datapath_gate(
        targeted_probe if isinstance(targeted_probe, dict) else None,
        cpe_cfg,
        top_d,
    )


def _filter_business_joint_causes_for_datapath_accuracy(
    causes: List[RootCause],
    allow_tunnel_inventory_overlay_causes: bool,
    targeted_business_all_ok: bool,
) -> List[RootCause]:
    """按「声明业务在 CPE 观测面是否出现目的地址 conntrack 命中」等过滤联合根因。

    ``allow_tunnel_inventory_overlay_causes`` 为真时保留 CPE-002 / OVERLAY-* 等隧道库存类卡片。
    """
    if allow_tunnel_inventory_overlay_causes:
        return causes
    out: List[RootCause] = []
    for c in causes:
        if c.cause_id in _TUNNEL_INVENTORY_CAUSE_IDS or c.cause_id.startswith("OVERLAY-"):
            continue
        if targeted_business_all_ok and c.cause_id in ("CPE-003", "CPE-004"):
            continue
        out.append(c)
    return out


def _infer_business_failure_stage(targeted_probe: Optional[dict]) -> dict:
    """从业务探测行提取“报文在哪一段失败”的摘要。"""
    data = (targeted_probe or {}).get("data") if isinstance(targeted_probe, dict) else {}
    rows = data.get("business_probes") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return {"stage": "unknown", "detail": "未找到业务探测行"}
    for row in rows:
        if not isinstance(row, dict):
            continue
        domain = str(row.get("domain") or "")
        port = row.get("port")
        dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
        if dns.get("status") not in ("ok",):
            return {
                "stage": "dns",
                "detail": f"{domain}:{port} 在 DNS 阶段失败（{dns.get('status') or 'unknown'}）",
            }
        tcp_rows = row.get("tcp") if isinstance(row.get("tcp"), list) else []
        for t in tcp_rows:
            if not isinstance(t, dict):
                continue
            if t.get("status") != "ok":
                return {
                    "stage": "tcp_connect",
                    "detail": (
                        f"{domain}:{port} 到 {t.get('host')} TCP 建连失败"
                        f"（{t.get('error') or t.get('status')}）"
                    ),
                }
            td = t.get("data") if isinstance(t.get("data"), dict) else {}
            if td.get("port_open") is False:
                return {
                    "stage": "server_port",
                    "detail": f"{domain}:{port} 到 {t.get('host')} 可达但目标端口未开放/拒绝",
                }
    # DNS+TCP 均无失败点时 ``stage`` 仍为 ok；ICMP 追踪摘要单独给出，供 JSON/模板阅读（不用于拓扑抑制）。
    trace_notes: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for tr in row.get("trace") or []:
            if not isinstance(tr, dict) or tr.get("status") != "ok":
                continue
            data = tr.get("data") if isinstance(tr.get("data"), dict) else {}
            summ = data.get("summary") if isinstance(data.get("summary"), dict) else {}
            if summ.get("target_reached"):
                continue
            host = str(tr.get("host") or "")
            th = int(summ.get("total_hops") or 0)
            if host:
                trace_notes.append(f"{host}: ICMP 追踪 {th} 跳未标示到达目标")
    out: dict[str, Any] = {"stage": "ok", "detail": "业务探测路径未发现明确失败点"}
    if trace_notes:
        out["trace_note"] = "; ".join(trace_notes[:4])
    return out


INTERNET_TERMINAL_NODE_ID = "internet-terminal"

_INTERNET_TERMINAL_NODE: dict[str, Any] = {
    "id": INTERNET_TERMINAL_NODE_ID,
    "name": "Internet",
    "type": "internet",
    "ip_address": None,
    "interfaces": [],
    "metadata": {
        "underlay_terminal": True,
        "terminal_note": "公网目标域示意（非 traceroute 单 hop）。",
    },
}


def _reconcile_joint_datapath_reading_layer(
    topo_dict: dict,
    gate: JointOverlayDatapathGate,
    presentation: JointTopologyPresentation,
    targeted_probe: Optional[dict],
) -> None:
    """在 ``resolve_joint_topology_presentation`` 之后校准与隧道/Overlay 相关的**阅读层**拓扑字段。

    ``compute_joint_overlay_datapath_gate`` 回答「证据上是否**允许**画隧道示意」；
    ``resolve_joint_topology_presentation`` 进一步约束「本 HTML 剖面是否**实际**画 Overlay 条带」
    （例如本机 DNS/TCP 全成功时强制互联网剖面、不画 CPE↔Hub）。

    当 ``gate.show_overlay_tunnel_strip`` 为真而 ``presentation.show_overlay_tunnel_strip`` 为假时，
    若仍保留 gate 生成的「将展示隧道示意条」类横幅，会与模板实际渲染矛盾，导致运维读者串读。
    本函数仅在上述分叉下覆写横幅/脚注，**不**改写 ``joint_overlay_rule_case``（仍保留引擎门控原始标签便于对账）。
    """
    tp = targeted_probe if isinstance(targeted_probe, dict) else None
    if presentation.show_overlay_tunnel_strip:
        return
    topo_dict["business_joint_suppress_overlay_topology_presentation"] = True
    if not gate.show_overlay_tunnel_strip:
        return
    if tp is None or not targeted_probe_business_rows_all_ok(tp):
        return
    topo_dict["declared_business_datapath_banner"] = (
        "【互联网核查剖面】本机声明目标 DNS/TCP 已通过；本报告拓扑不展示 CPE↔Hub 隧道示意条。"
        " 设备侧 nf_conntrack 等采样仅作佐证，**不等于**该探测流必经 Overlay/隧道面；隧道库存与策略链专检请用 deep-dive。"
    )
    topo_dict["joint_overlay_topology_note"] = ""
    topo_dict["joint_overlay_suppress_reason"] = (
        "阅读层已与 ``topology_joint_presentation`` 对齐：探测全通时不在本报告绑定隧道示意条（保留 Underlay 公网域示意）。"
    )
    topo_dict["declared_business_datapath_verdict"] = "unverified"


def finalize_business_topology_joint_report(
    topology_dict: dict,
    presentation: JointTopologyPresentation,
) -> None:
    """业务联合报告专用：按 ``JointTopologyPresentation`` 裁剪 Underlay、追加 Internet 终点。

    在 ``_annotate_problem_nodes`` 之后调用；**不得**在此覆盖 ``compute_joint_overlay_datapath_gate`` 的
    Overlay 展示决策（避免「互联网 Underlay + SD-WAN Overlay」双剖面冲突）。
    """
    items_in = topology_dict.get("layout_underlay_items")
    if not isinstance(items_in, list) or not items_in:
        return

    topology_dict["topology_display_variant"] = presentation.variant
    topology_dict["topology_presentation_note"] = presentation.narrative_coherence_note
    topology_dict["business_joint_suppress_overlay_topology_presentation"] = (
        not presentation.show_overlay_tunnel_strip
    )
    pc_id = topology_dict.get("pc_node_id")
    cpe_id = topology_dict.get("cpe_node_id")
    gw_id = topology_dict.get("gateway_node_id")
    hub_id = topology_dict.get("hub_node_id")

    items: list[dict[str, Any]] = list(items_in)
    pids = {str(x) for x in (topology_dict.get("problem_node_ids") or []) if x}
    underlay_pids: set[str] = set(pids)
    if presentation.path_focus_beyond_sdwan:
        for skip in (cpe_id, gw_id, hub_id):
            if skip:
                pids.discard(str(skip))
                underlay_pids.discard(str(skip))
    stage_ok = (topology_dict.get("business_failure_stage") or {}).get("stage") == "ok"

    if (
        pids
        and not stage_ok
        and presentation.trim_underlay_at_first_problem_node
    ):
        cut: Optional[int] = None
        for i, it in enumerate(items):
            if not isinstance(it, dict) or it.get("kind") != "node":
                continue
            nid = (it.get("node") or {}).get("id")
            if nid and str(nid) in pids:
                cut = i + 1
                break
        if cut is not None:
            items = items[:cut]
            topology_dict["topology_underlay_trimmed"] = True
    else:
        topology_dict.pop("topology_underlay_trimmed", None)

    last = items[-1] if items else None
    last_nid: Optional[str] = None
    last_type: Optional[str] = None
    if isinstance(last, dict) and last.get("kind") == "node":
        n = last.get("node") or {}
        last_nid = str(n.get("id") or "")
        last_type = str(n.get("type") or "")

    append_terminal = False
    if last_nid and last_nid != INTERNET_TERMINAL_NODE_ID and last_nid != pc_id:
        if presentation.variant == "sdwan" and last_type in ("cpe", "gateway"):
            append_terminal = True
        elif presentation.variant == "internet" and last_type in ("cpe", "gateway", "hub"):
            append_terminal = True

    if append_terminal and last_nid:
        # 仅在本机业务探测未达「ok」时把末跳→公网域标为故障示意；探测已通过时不得因 traceroute/旁证
        # 仍标红公网域（否则与「核查通过」及链路上无应用故障矛盾）。
        fault_hop = bool(
            not stage_ok
            and (
                presentation.underlay_fault_on_internet_ingress
                or topology_dict.get("business_fault_beyond_tunnel_edge")
                or (topology_dict.get("business_failure_stage") or {}).get("stage") == "server_port"
            )
        )
        items.append(
            {
                "kind": "hop",
                "connection": "indirect",
                "source_id": last_nid,
                "target_id": INTERNET_TERMINAL_NODE_ID,
                "edge_key": f"{last_nid}->{INTERNET_TERMINAL_NODE_ID}",
                "problem": fault_hop,
            }
        )
        items.append({"kind": "node", "node": dict(_INTERNET_TERMINAL_NODE)})
        if fault_hop:
            underlay_pids.add(INTERNET_TERMINAL_NODE_ID)

    topology_dict["layout_underlay_items"] = items
    topology_dict["topology_underlay_problem_node_ids"] = sorted(underlay_pids)


def _annotate_problem_nodes(
    topology_dict: dict,
    causes: List[RootCause],
    targeted_probe: Optional[dict],
    *,
    cpe_configuration: Optional[Any] = None,
    presentation: Optional[JointTopologyPresentation] = None,
) -> None:
    """把问题节点和故障阶段写入 topology dict，供 deep_dive 模板高亮。

    当隧道 peer ICMP 全通且 nf_conntrack 对业务目的 IP 呈 SYN-only 时，更符合「问题在对端以远」，
    此时不再把 Overlay 隧道段、CPE 侧策略/ NAT 告警标成与「隧道断」等价的拓扑故障样式，避免与商用摘要矛盾。

    当 ``targeted_probe`` 中业务探测行在 ``_infer_business_failure_stage`` 下为 **ok** 时，**仅抑制**与「声明目标
    已达通」明显矛盾的拓扑着色：不在 Underlay 上因 **CPE-003/CPE-004**（配置启发式）或 **BIZ-*** 再标 PC↔CPE
    业务路径红段；**不**以此清空 **CPE-001**、**RAISECOM-LINK-PROT-001** 等基础设施类根因的标记，也不改写
    **CPE-002/OVERLAY** 在 ``path_beyond_tunnel_likely`` 下的既有抑制逻辑。

    每次调用会先清除 ``edges`` / ``layout_underlay_items`` 上已有的 ``problem`` 标记，再按当前 ``causes`` 重算，
    避免残留边与本轮规则不一致。
    """
    nodes = topology_dict.get("nodes") or []
    edges = topology_dict.get("edges") or []
    node_ids = {str(n.get("id")) for n in nodes if isinstance(n, dict) and n.get("id")}
    edge_keys = {
        f"{e.get('source_id')}->{e.get('target_id')}"
        for e in edges
        if isinstance(e, dict) and e.get("source_id") and e.get("target_id")
    }
    pc_id = topology_dict.get("pc_node_id")
    cpe_id = topology_dict.get("cpe_node_id")
    gw_id = topology_dict.get("gateway_node_id")
    hub_id = topology_dict.get("hub_node_id")

    stage_info = _infer_business_failure_stage(targeted_probe)
    topology_dict["business_failure_stage"] = stage_info
    business_path_ok = stage_info.get("stage") == "ok"

    if isinstance(topology_dict.get("layout_underlay_items"), list):
        for item in topology_dict["layout_underlay_items"]:
            if isinstance(item, dict):
                item.pop("problem", None)
    if isinstance(edges, list):
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            edge.pop("problem", None)
            edge.pop("problem_reason", None)
            edge.pop("problem_layer", None)

    ev = joint_datapath_evidence_from_targeted_probe(targeted_probe)
    trace_ev = analyze_business_trace_evidence(
        targeted_probe, cpe_configuration, topology_dict
    )
    topology_dict["business_trace_evidence"] = trace_ev.as_dict()
    pbt = bool(ev and path_beyond_tunnel_likely(ev))
    beyond_edge = failure_beyond_sdwan_edge_likely(
        targeted_probe,
        ev,
        cpe_configuration=cpe_configuration,
        topology_dict=topology_dict,
    )
    path_focus_beyond = pbt or beyond_edge
    presentation_focus_beyond = bool(
        presentation.path_focus_beyond_sdwan if presentation is not None else False
    )
    suppress_focus = path_focus_beyond or presentation_focus_beyond
    suppress_heuristic_topo = bool(
        presentation.suppress_heuristic_cpe_underlay_markers
        if presentation is not None
        else suppress_focus
    )

    markers: list[dict[str, str]] = []
    edge_markers: list[dict[str, str]] = []

    def add_marker(node_id: Optional[str], reason: str, layer: str) -> None:
        if not node_id or node_id not in node_ids:
            return
        if any(m["node_id"] == node_id and m["reason"] == reason for m in markers):
            return
        markers.append({"node_id": node_id, "reason": reason, "layer": layer})

    def add_edge_marker(source_id: Optional[str], target_id: Optional[str], reason: str, layer: str) -> None:
        if not source_id or not target_id:
            return
        key = f"{source_id}->{target_id}"
        if key not in edge_keys:
            return
        if any(m["edge_key"] == key and m["reason"] == reason for m in edge_markers):
            return
        edge_markers.append(
            {"edge_key": key, "source_id": source_id, "target_id": target_id, "reason": reason, "layer": layer}
        )

    for c in causes:
        cid = c.cause_id
        if cid.startswith("BIZ-DNS"):
            if business_path_ok:
                continue
            add_marker(pc_id, c.title, "dns")
            add_edge_marker(pc_id, cpe_id, c.title, "dns")
        elif cid in ("CPE-001", "RAISECOM-LINK-PROT-001"):
            add_marker(cpe_id, c.title, "cpe")
            add_edge_marker(pc_id, cpe_id, c.title, "cpe")
        elif cid in ("CPE-003", "CPE-004"):
            if suppress_heuristic_topo or business_path_ok:
                continue
            add_marker(cpe_id, c.title, "cpe")
            add_edge_marker(pc_id, cpe_id, c.title, "cpe")
        elif cid.startswith("CPE-002") or cid.startswith("OVERLAY-"):
            if suppress_focus and (cid == "CPE-002-WARN" or cid.startswith("OVERLAY-")):
                continue
            add_marker(cpe_id, c.title, "overlay")
            add_marker(hub_id, c.title, "overlay")
            add_edge_marker(cpe_id, hub_id, c.title, "overlay")
        elif cid.startswith("BIZ-TCP"):
            if business_path_ok:
                continue
            stage = stage_info.get("stage")
            if stage == "server_port":
                # 端口未开放/拒绝：问题语义在「业务目的网侧 / 远端服务」，不在 CPE↔WAN 物理上行段。
                # 若在 gw/hub 上打 problem 标记，链路一览会把 cpe→gw 标红（ingress 命中 problem 节点），与事实串线。
                # Underlay 末跳→公网域由 ``finalize_business_topology_joint_report`` 按 ``server_port`` 着色。
                continue
            elif suppress_focus:
                pass
            else:
                add_marker(cpe_id or gw_id, c.title, "tcp-path")
                add_edge_marker(pc_id, cpe_id, c.title, "tcp-path")
                add_edge_marker(cpe_id, gw_id, c.title, "tcp-path")
                add_edge_marker(cpe_id, hub_id, c.title, "tcp-path")

    topology_dict["problem_markers"] = markers
    topology_dict["problem_node_ids"] = [m["node_id"] for m in markers]
    topology_dict["problem_edge_markers"] = edge_markers
    topology_dict["problem_edge_keys"] = [m["edge_key"] for m in edge_markers]
    topology_dict["business_fault_beyond_tunnel_edge"] = path_focus_beyond
    overlay_key_for_ov: Optional[str] = None
    if cpe_id and hub_id:
        overlay_key_for_ov = f"{cpe_id}->{hub_id}"
        ov = next(
            (
                m
                for m in edge_markers
                if m["edge_key"] == overlay_key_for_ov and m.get("layer") == "overlay"
            ),
            None,
        )
        if ov is not None:
            topology_dict["overlay_problem"] = {
                "edge_key": overlay_key_for_ov,
                "reason": ov["reason"],
                "layer": ov["layer"],
            }
        else:
            topology_dict["overlay_problem"] = None
    else:
        topology_dict["overlay_problem"] = None

    problem_targets = {str(x) for x in topology_dict["problem_node_ids"] if x}
    overlay_only_underlay = bool(topology_dict.get("overlay_problem")) and bool(edge_markers) and all(
        m.get("layer") == "overlay" for m in edge_markers
    )
    hop_idx = 0
    if edge_markers and isinstance(topology_dict.get("layout_underlay_items"), list):
        for item in topology_dict["layout_underlay_items"]:
            if not isinstance(item, dict) or item.get("kind") != "hop":
                continue
            hop_idx += 1
            key = item.get("edge_key")
            tid = item.get("target_id")
            sid = item.get("source_id")
            if not key or key not in topology_dict["problem_edge_keys"]:
                continue
            if overlay_only_underlay:
                continue
            ingress_to_problem = bool(tid and str(tid) in problem_targets)
            first_hop_src_problem = bool(
                hop_idx == 1 and sid and str(sid) in problem_targets
            )
            if not ingress_to_problem and not first_hop_src_problem:
                continue
            item["problem"] = True
    if isinstance(edges, list):
        lookup = {m["edge_key"]: m for m in edge_markers}
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            k = f"{edge.get('source_id')}->{edge.get('target_id')}"
            if k in lookup:
                m = lookup[k]
                if suppress_focus and (
                    edge.get("link_type") == "tunnel"
                    or m.get("layer") in ("beyond-peer", "overlay")
                ):
                    continue
                edge["problem"] = True
                edge["problem_reason"] = m["reason"]
                edge["problem_layer"] = m["layer"]


def _severity_from_causes(
    causes: List[RootCause],
    probe_status: str,
    *,
    business_probe_all_ok: bool = False,
) -> Severity:
    """由根因列表与探针状态汇总报告严重度。

    当本机声明目标 DNS/TCP 已全部成功时，不把配置启发式（如 CPE-003）抬成 ERROR 级摘要，
    除非存在 CPE 管理面不可达（CPE-001）等硬故障。
    """
    sev = Severity.INFO
    if causes:
        if any(c.severity == Severity.CRITICAL for c in causes):
            sev = Severity.CRITICAL
        elif any(c.severity == Severity.ERROR for c in causes):
            sev = Severity.ERROR
        elif any(c.severity == Severity.WARNING for c in causes):
            sev = Severity.WARNING
    elif probe_status == "partial":
        sev = Severity.WARNING

    if business_probe_all_ok and not any(c.cause_id == "CPE-001" for c in causes):
        if sev == Severity.ERROR:
            return Severity.WARNING
        if sev == Severity.CRITICAL:
            return Severity.WARNING
        if sev == Severity.WARNING:
            return Severity.INFO
    if probe_status == "partial" and sev == Severity.INFO:
        return Severity.WARNING
    return sev


def _build_cpe_collector(
    cpe_host: str,
    cpe_port: int,
    cpe_user: str,
    password: Optional[str],
    key_file: Optional[str],
    protocol: str,
    credentials_file: Optional[Path],
    view_credentials_file: Optional[Path],
    verbose: bool,
) -> CpeCollector:
    cred_path = credentials_file if credentials_file is not None else default_cpe_credentials_path()
    file_creds = load_device_credentials_file(cred_path, cpe_host)
    login_password = password if password else file_creds.get("password")
    testnode_password = file_creds.get("testnode_password")
    if verbose and cred_path.is_file():
        logger.debug("已加载 CPE 凭证文件: %s", cred_path)

    view_cred_path = (
        view_credentials_file
        if view_credentials_file is not None
        else default_cpe_view_credentials_path()
    )
    view_presets = load_view_credentials_file(view_cred_path)
    if verbose and view_cred_path.is_file():
        logger.debug("已加载通用视图口令文件: %s", view_cred_path)

    cfg = CpeCollectorConfig(
        host=cpe_host,
        port=cpe_port,
        username=cpe_user,
        password=login_password,
        private_key=key_file,
        protocol=protocol,
        testnode_password=testnode_password,
        preset_view_passwords=view_presets,
    )
    return CpeCollector(config=cfg)


def _write_joint_deep_dive_style_report(
    *,
    trace_id: str,
    diagnosis: DiagnosisResult,
    topology: Any,
    cpe_result: Any,
    targeted_probe: Optional[dict],
    pc_snapshot: Any,
    out_path: Path,
    joint_failure_driven: bool,
    overlay_policy_flow: Optional[dict] = None,
    underlay_declared_business_focus: bool = False,
    biz_targets: Optional[List[str]] = None,
) -> str:
    from sdwan_desktop.interface.cli.commands.deep_dive import _enrich_topology_report_dict

    builder = HtmlReportBuilder()
    topo_dict = topology.to_dict()
    _enrich_topology_report_dict(topo_dict)

    if joint_failure_driven:
        topo_dict["report_html_title"] = "SD-WAN 业务路径联合诊断报告（探测失败场景）"
        topo_dict["report_html_h1"] = "业务路径联合诊断报告"
        topo_dict["report_html_h1_note"] = (
            "本机业务探测未通过；已叠加 PC 快照、CPE 采集与拓扑联合分析。"
        )
        topo_dict["report_diagnosis_label"] = "业务路径联合分析（探测失败驱动）"
    else:
        topo_dict["report_html_title"] = "SD-WAN 业务路径联合核查报告（本机探测已通过）"
        topo_dict["report_html_h1"] = "业务路径联合核查报告"
        topo_dict["report_html_h1_note"] = (
            "本机 DNS/TCP 探测已成功；以下为 CPE 侧端到端核查与拓扑对照。"
        )
        topo_dict["report_diagnosis_label"] = "业务路径联合核查（本机探测已通过）"

    report_hints: list[str] = []
    report_hints.extend(topo_dict.get("topology_notes") or [])
    topo_dict["targeted_probe"] = targeted_probe or {}

    cpe_cfg = None
    if cpe_result and cpe_result.success and isinstance(cpe_result.data, dict):
        cpe_cfg = cpe_result.data.get("cpe_configuration")

    gate = compute_joint_overlay_datapath_gate(
        targeted_probe if isinstance(targeted_probe, dict) else None,
        cpe_cfg,
        topo_dict,
    )
    tp_dict = targeted_probe if isinstance(targeted_probe, dict) else None
    has_ct = targeted_probe_has_business_target_conntrack_hits(tp_dict)
    topo_dict["declared_business_datapath_verdict"] = (
        "overlay_evidence_positive" if gate.overlay_evidence_positive else "unverified"
    )
    topo_dict["report_joint_nf_conntrack_had_session_lines"] = has_ct
    topo_dict["business_joint_suppress_overlay_topology_presentation"] = (
        not gate.show_overlay_tunnel_strip
    )
    if gate.show_overlay_tunnel_strip:
        topo_dict["joint_overlay_suppress_reason"] = ""
    elif getattr(gate, "presentation_suppress_detail", ""):
        topo_dict["joint_overlay_suppress_reason"] = gate.presentation_suppress_detail
    elif has_ct:
        topo_dict["joint_overlay_suppress_reason"] = (
            "本轮 conntrack 已采样到声明目的地址会话，但未满足产品规则中展示隧道示意的条件。"
            "请结合会话双向元组、FIB 表 99/100 与 traceroute 跳表明细复核。"
        )
    else:
        topo_dict["joint_overlay_suppress_reason"] = (
            "本轮对声明业务目的地址的 nf_conntrack 采样未见非空会话行"
        )
    topo_dict["declared_business_datapath_banner"] = gate.datapath_banner
    topo_dict["joint_overlay_topology_note"] = gate.joint_overlay_topology_note
    topo_dict["joint_overlay_rule_case"] = gate.rule_case
    topo_dict["joint_evidence_tier"] = gate.evidence_tier
    topo_dict["joint_egress_shape"] = gate.egress_shape
    topo_dict["show_business_flow_overlay"] = gate.show_business_flow_overlay
    if gate.url_group_supplement:
        topo_dict["url_group_priority_supplement"] = gate.url_group_supplement

    if cpe_cfg is not None:
        from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
            is_raisecom_msg5200b_cpe,
        )

        if is_raisecom_msg5200b_cpe(cpe_cfg):
            from sdwan_desktop.services.diagnosis.raisecom_msg5200b_path_verdict import (
                build_joint_path_evidence_dict,
            )

            topo_dict["joint_path_evidence"] = build_joint_path_evidence_dict(
                tp_dict, cpe_cfg, topo_dict, gate
            )

    tp_dict_pres = targeted_probe if isinstance(targeted_probe, dict) else None
    biz_probe_all_ok = (
        targeted_probe_business_rows_all_ok(tp_dict_pres) if tp_dict_pres is not None else False
    )
    presentation = resolve_joint_topology_presentation(
        topology_dict=topo_dict,
        targeted_probe=tp_dict_pres,
        gate=gate,
        cpe_configuration=cpe_cfg,
        business_probe_all_ok=biz_probe_all_ok,
    )
    topo_dict["topology_joint_presentation"] = {
        "variant": presentation.variant,
        "show_overlay_tunnel_strip": presentation.show_overlay_tunnel_strip,
        "show_business_flow_overlay": gate.show_business_flow_overlay,
        "path_focus_beyond_sdwan": presentation.path_focus_beyond_sdwan,
        "business_probe_all_ok": biz_probe_all_ok,
        "narrative_coherence_note": presentation.narrative_coherence_note,
        "evidence_tier": gate.evidence_tier,
        "egress_shape": gate.egress_shape,
    }
    _reconcile_joint_datapath_reading_layer(
        topo_dict, gate, presentation, targeted_probe if isinstance(targeted_probe, dict) else None
    )

    _annotate_problem_nodes(
        topo_dict,
        diagnosis.root_causes,
        targeted_probe,
        cpe_configuration=cpe_cfg,
        presentation=presentation,
    )
    finalize_business_topology_joint_report(topo_dict, presentation)

    if cpe_cfg is not None:
        wan = cpe_cfg.wan_interfaces
        report_hints.extend(
            [
                f"CPE 主机名: {cpe_cfg.hostname}",
                f"设备: {cpe_cfg.model} · 软件 {cpe_cfg.version}",
            ]
        )
        # 业务路径联合报告：不在 hints 中罗列「VPN 隧道条数」——与声明单流路径无实证关联时易误读为业务必经隧道。
        if wan:
            report_hints.append(
                "WAN: " + ", ".join(f"{i.name} → {i.ip_address or '—'}" for i in wan[:6])
            )
    if pc_snapshot is not None:
        topo_dict["pc_snapshot_included"] = True
        report_hints.append("已纳入 PC 快照摘要（网卡 / 路由 / DNS / 代理）参与联合根因分析。")
    else:
        topo_dict["pc_snapshot_included"] = False
    if report_hints:
        topo_dict["hints"] = report_hints

    # 与 ``topology_joint_presentation`` / ``_reconcile_joint_datapath_reading_layer`` 对齐：探测全通且剖面已隐藏
    # Overlay 时，不把 Overlay 策略证据链块塞进 HTML（避免「无隧道条带却有长 Overlay 清单」）。
    effective_underlay_declared_focus = bool(
        underlay_declared_business_focus
        or (
            tp_dict is not None
            and targeted_probe_business_rows_all_ok(tp_dict)
            and not presentation.show_overlay_tunnel_strip
        )
    )

    if (
        isinstance(overlay_policy_flow, dict)
        and overlay_policy_flow.get("data")
        and not effective_underlay_declared_focus
    ):
        topo_dict["overlay_policy_flow"] = overlay_policy_flow

    delivery = build_commercial_delivery_payload(
        trace_id=trace_id,
        diagnosis=diagnosis,
        topology_dict=topo_dict,
        targeted_probe=targeted_probe,
        underlay_declared_business_focus=effective_underlay_declared_focus,
    )
    if delivery is not None:
        topo_dict["commercial_delivery"] = delivery.as_template_dict()

    gen_targets = [str(x).strip() for x in (biz_targets or []) if str(x).strip()]
    if not gen_targets:
        gen_targets = biz_targets_from_targeted_probe(
            targeted_probe if isinstance(targeted_probe, dict) else None
        )
    topo_dict["report_html_business_targets"] = gen_targets
    topo_dict["report_html_business_targets_line"] = "、".join(gen_targets) if gen_targets else ""

    topo_dict["report_joint_probe_outcome"] = build_joint_report_probe_outcome(
        biz_targets=gen_targets,
        targeted_probe=targeted_probe if isinstance(targeted_probe, dict) else None,
        diagnosis=diagnosis,
        joint_failure_driven=joint_failure_driven,
        business_failure_stage=topo_dict.get("business_failure_stage"),
        business_fault_beyond_tunnel_edge=bool(
            topo_dict.get("business_fault_beyond_tunnel_edge")
        ),
    )
    if pc_snapshot is not None and hasattr(pc_snapshot, "to_json_dict"):
        topo_dict["pc_snapshot"] = pc_snapshot.to_json_dict()
    else:
        topo_dict["pc_snapshot"] = None

    topo_dict["report_pack"] = build_business_diagnose_pack(
        result=diagnosis,
        joint_mode=True,
        biz_targets=gen_targets,
        joint_failure_driven=joint_failure_driven,
    ).as_template_dict()

    return builder.build_deep_dive_report(diagnosis, topo_dict, out_path)


@click.command(
    "business-diagnose",
    epilog=(
        "成功判据: 本机 DNS/TCP 探测完成（可选 ICMP traceroute 作路径旁证）；联合模式另含 CPE 采集与拓扑报告生成。\n"
        "不包含: 与声明目标无关的全量 CPE 配置审计（请用 deep-dive）。\n"
        "升级: 本机初判 → quick-check；全设备专检 → deep-dive。\n"
        "JSON（-F json）: 顶层含 report_pack（商用元数据）与 diagnosis。\n"
        "退出码: 0 成功；2 缺 CPE 且探测失败；1 其它错误。"
    ),
)
@click.option(
    "--biz-target",
    "-b",
    "biz_target",
    multiple=True,
    required=True,
    help="业务探测目标 FQDN:TCP端口，可多次；-b 等价。省略端口时默认 443。",
)
@click.option(
    "--biz-dns-server",
    "-S",
    "biz_dns_server",
    default=None,
    metavar="IPV4",
    help="业务 DNS 解析服务器 IPv4（可选；-S 为短名）。",
)
@click.option("--output", "-o", "output", default=None, help="报告输出路径（默认 ./reports/）。")
@click.option(
    "--format",
    "-F",
    "fmt",
    type=click.Choice(["html", "json"], case_sensitive=False),
    default="html",
    help="输出格式：html 或 json（短选项 -F 大写，与凭证类 -f 区分）。",
)
@click.option(
    "--no-traceroute",
    is_flag=True,
    default=False,
    help="跳过本机路由追踪（默认对解析到的 IPv4 执行 traceroute，作路径旁证）。",
)
@click.option(
    "--collect-pc/--no-collect-pc",
    default=True,
    help="默认采集本机快照（与 --no-collect-pc 跳过）；跳过则根因置信度受限。",
)
@click.option(
    "--cpe-host",
    "-c",
    "cpe_host",
    default=None,
    metavar="IP",
    help=(
        "CPE 管理面 IP：业务探测未通过且未使用 --allow-probe-only 时必填，用于联合分析。"
        "业务探测已全部成功时若仍提供本参数与 --username，将采集 CPE 并生成含业务流拓扑的端到端核查报告。"
    ),
)
@click.option(
    "--port",
    "-p",
    "cpe_port",
    default=23,
    help="CPE 连接端口（默认 23，Telnet 常用）。",
)
@click.option(
    "--username",
    "--user",
    "-u",
    "cpe_user",
    default=None,
    metavar="NAME",
    help="CPE 登录用户名（与 --cpe-host 同时使用时必填）。",
)
@click.option(
    "--password",
    default=None,
    help="CPE 登录密码（或使用 --key-file；亦可放在凭证 YAML 中）。",
)
@click.option("--key-file", "-k", "key_file", default=None, help="SSH 私钥路径。")
@click.option(
    "--protocol",
    "-P",
    "protocol",
    default="telnet",
    type=click.Choice(["telnet", "ssh"], case_sensitive=False),
    help="CPE 连接协议（默认 telnet）。",
)
@click.option(
    "--credentials-file",
    "-f",
    type=click.Path(exists=False, path_type=Path, dir_okay=False),
    default=None,
    help="CPE 设备凭证 YAML（与 deep-dive 相同）。",
)
@click.option(
    "--view-credentials-file",
    "-V",
    type=click.Path(exists=False, path_type=Path, dir_okay=False),
    default=None,
    help="固定视图通用口令 YAML（与 deep-dive 相同）。",
)
@click.option(
    "--allow-probe-only",
    is_flag=True,
    default=False,
    help="业务探测失败时仍只输出本机探针层结论（不推荐；默认将要求 CPE 联合分析）。",
)
@click.option("--verbose", "-v", is_flag=True, help="详细日志。")
def business_diagnose(
    biz_target: Tuple[str, ...],
    biz_dns_server: Optional[str],
    output: Optional[str],
    fmt: str,
    collect_pc: bool,
    no_traceroute: bool,
    cpe_host: Optional[str],
    cpe_port: int,
    cpe_user: Optional[str],
    password: Optional[str],
    key_file: Optional[str],
    protocol: str,
    credentials_file: Optional[Path],
    view_credentials_file: Optional[Path],
    allow_probe_only: bool,
    verbose: bool,
) -> None:
    """本机业务路径诊断：DNS(A)+TCP+可选 traceroute。

    探测失败时在提供 CPE 参数条件下继续 PC+CPE+拓扑联合分析。探测已成功时若仍提供
    ``--cpe-host`` 与 ``--username``，将采集 CPE 并输出含业务流拓扑的端到端核查报告（深度诊断模板）。
    Traceroute 不单独触发「须联合」门控（见 ``business_probe_requires_joint_diagnosis``）。
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Windows 控制台默认代码页易导致中文步骤与 SKIP 说明乱码；尽量切到 UTF-8 输出。
    if sys.platform == "win32":
        for _stream in (sys.stdout, sys.stderr):
            if hasattr(_stream, "reconfigure"):
                try:
                    _stream.reconfigure(encoding="utf-8")
                except (AttributeError, OSError, ValueError):
                    pass

    try:
        specs = parse_biz_target_tokens(biz_target)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if cpe_host and not (cpe_user and cpe_user.strip()):
        raise click.UsageError("使用 --cpe-host / -c 时必须同时提供 --username / -u。")

    trace_id = str(uuid.uuid4())
    print("SD-WAN 业务不通诊断（本机）")
    print(f"Trace ID: {trace_id}")
    print("")

    ctx = FlowContext(trace_id=trace_id)
    cpe_ready = bool(cpe_host and cpe_user and cpe_user.strip())
    ctx.set("cpe_ready", cpe_ready)
    ctx.set("allow_probe_only", allow_probe_only)
    ctx.set("collect_pc", collect_pc)
    ctx.set("biz_specs", specs)
    ctx.set("biz_dns_server", biz_dns_server)
    ctx.set("cpe_mgmt_ip", str(cpe_host or ""))
    if cpe_ready:
        # 预建采集器与拓扑构建器，供 step-joint 调用 followup（与 deep-dive 联合阶段同源）
        ctx.set(
            "_cpe_collector",
            _build_cpe_collector(
                cpe_host,
                cpe_port,
                cpe_user.strip(),
                password,
                key_file,
                protocol,
                credentials_file,
                view_credentials_file,
                verbose,
            ),
        )
        ctx.set("_topology_builder", TopologyBuilder())
    else:
        ctx.set("_cpe_collector", None)
        ctx.set("_topology_builder", None)

    async def step_pc_collect(ctx: FlowContext) -> Any:
        print("[1/6] PC 端信息采集... ", end="", flush=True)
        if not ctx.get("collect_pc", True):
            ctx.set("pc_snapshot", None)
            print("SKIP")
            return None
        collector = WindowsCollector()
        snap = await collector.collect(ctx)
        ctx.set("pc_snapshot", snap)
        print("OK")
        return snap

    async def step_biz_probe(ctx: FlowContext) -> BusinessDiagnosisOutcome:
        print("[2/6] 业务 DNS/TCP/Traceroute 探测... ", end="", flush=True)
        specs_inner: List[BizDomainPortSpec] = ctx.get("biz_specs")
        outcome = await orchestrate_business_domain_port_diagnosis(
            ctx,
            specs_inner,
            ctx.get("biz_dns_server"),
            None,
            compare_system_dns=bool(ctx.get("biz_dns_server")),
            enable_traceroute=not no_traceroute,
        )
        ctx.set("business_outcome", outcome)
        jn = business_probe_requires_joint_diagnosis(outcome)
        ctx.set("joint_needed", jn)
        run_joint = bool(ctx.get("cpe_ready")) and (
            (not jn) or (jn and not ctx.get("allow_probe_only"))
        )
        ctx.set("run_joint", run_joint)
        print("OK")
        return outcome

    async def step_validate_joint_prereq(ctx: FlowContext) -> None:
        print("[3/6] 联合分析前置校验... ", end="", flush=True)
        if not ctx.get("joint_needed"):
            print("OK")
            return None
        if ctx.get("allow_probe_only"):
            print("OK")
            return None
        if ctx.get("cpe_ready"):
            print("OK")
            return None
        msg = (
            "业务探测未全部成功。要输出基于 PC、CPE 与拓扑的证据链结论（区分本机、CPE、"
            "隧道/策略与对端无响应等），请提供 CPE 管理地址与登录参数，例如：\n"
            f"  agentctl business-diagnose -b <FQDN:端口> --cpe-host <CPE_IP> --username <USER> "
            f"[--password …] [--protocol ssh] [--port 22]\n"
            "或执行全量深度诊断：\n"
            f"  agentctl deep-dive -c <CPE_IP> -u <USER> … -b <FQDN:端口>\n"
            "若仅需本机探针层结论文档，请加：--allow-probe-only"
        )
        print(msg, file=sys.stderr)
        raise SystemExit(2)

    async def step_biz_rca(ctx: FlowContext) -> List[RootCause]:
        print("[4/6] 本机业务 RCA... ", end="", flush=True)
        collect = bool(ctx.get("collect_pc", True))
        pc_snapshot = ctx.get("pc_snapshot") if collect else None
        outcome: BusinessDiagnosisOutcome = ctx.get("business_outcome")
        obs = build_observation_standalone(ctx.trace_id, pc_snapshot if collect else None)
        bundle = ProbeBundle(trace_id=ctx.trace_id, business_probes=list(outcome.business_probes))
        causes_local = BusinessRCAEngine().analyze(obs, bundle)
        ctx.set("causes_local", causes_local)
        print("OK")
        return causes_local

    async def step_joint(ctx: FlowContext) -> Any:
        print("[5/6] CPE 联合采集与拓扑... ", end="", flush=True)
        if not ctx.get("run_joint"):
            ctx.set("joint_done", False)
            ctx.set("causes", ctx.get("causes_local", []))
            ctx.set("topology", None)
            ctx.set("cpe_result", None)
            ctx.set("targeted_probe", None)
            print("SKIP")
            return None
        cpe_collector_inner = ctx.get("_cpe_collector")
        topology_builder_inner = ctx.get("_topology_builder")
        cpe_mgmt = str(ctx.get("cpe_mgmt_ip") or "")
        outcome: BusinessDiagnosisOutcome = ctx.get("business_outcome")
        pc_snapshot = ctx.get("pc_snapshot") if ctx.get("collect_pc") else None
        try:
            topology, cpe_result, targeted_probe, causes = await run_joint_root_cause_after_business_probe(
                ctx,
                pc_snapshot,
                outcome,
                cpe_collector=cpe_collector_inner,
                topology_builder=topology_builder_inner,
                cpe_mgmt_ip=cpe_mgmt,
            )
        except Exception as exc:
            logger.error("CPE/拓扑联合分析失败: %s", exc, exc_info=True)
            print(f"CPE/拓扑联合分析失败: {exc}")
            sys.exit(1)
        ctx.set("joint_done", True)
        ctx.set("topology", topology)
        ctx.set("cpe_result", cpe_result)
        ctx.set("targeted_probe", targeted_probe)
        ctx.set("causes", causes)
        print("OK")
        return causes

    async def step_overlay(ctx: FlowContext) -> Any:
        if not ctx.get("run_joint"):
            # 未跑 CPE 联合时无 ``cpe_result``/拓扑后信封，归纳步骤无输入；避免向仅本机报告注入空证据链块。
            ctx.set("overlay_policy_flow", None)
            print("[6/6] Overlay 与策略分流证据链... SKIP（未跑 CPE 联合）")
            return None
        tp_overlay = ctx.get("targeted_probe")
        cpe_res = ctx.get("cpe_result")
        topo = ctx.get("topology")
        cpe_cfg = None
        if cpe_res and getattr(cpe_res, "success", False) and isinstance(cpe_res.data, dict):
            cpe_cfg = cpe_res.data.get("cpe_configuration")
        top_d = topo.to_dict() if topo is not None and hasattr(topo, "to_dict") else None
        if isinstance(tp_overlay, dict) and not business_joint_should_present_overlay_tunnel_narrative(
            tp_overlay,
            cpe_configuration=cpe_cfg,
            topology_dict=top_d,
        ):
            logger.info(
                "业务路径诊断：声明目标语境下跳过 Overlay/策略分流证据链（underlay/公网聚焦）"
            )
            ctx.set("overlay_policy_flow", None)
            print("[6/6] Overlay 与策略分流证据链... SKIP（未证实声明流经 Overlay/隧道面）")
            return None
        print("[6/6] Overlay 与策略分流证据链... ", end="", flush=True)
        await run_overlay_policy_flow_step(ctx)
        print("OK")
        return ctx.get("overlay_policy_flow")

    handlers = {
        "step-pc-collect": step_pc_collect,
        "step-biz-probe": step_biz_probe,
        "step-validate-joint-prereq": step_validate_joint_prereq,
        "step-biz-rca": step_biz_rca,
        "step-joint-cpe-topology": step_joint,
        "step-overlay-policy-flow": step_overlay,
    }

    try:
        runtime = FlowRuntime()
        asyncio.run(runtime.execute_flow(BUSINESS_DIAGNOSE_FLOW, ctx, handlers))
    except SystemExit:
        raise
    except Exception as exc:
        logger.error("业务诊断流程执行失败: %s", exc, exc_info=True)
        print(f"执行失败: {exc}")
        sys.exit(1)

    outcome = ctx.get("business_outcome")
    pc_snapshot = ctx.get("pc_snapshot")
    joint_done = bool(ctx.get("joint_done"))
    joint_needed = bool(ctx.get("joint_needed"))
    topology = ctx.get("topology")
    cpe_result = ctx.get("cpe_result")
    targeted_probe = ctx.get("targeted_probe")
    causes: List[RootCause] = list(ctx.get("causes") or ctx.get("causes_local", []))
    if joint_done and causes:
        from sdwan_desktop.services.analyzer.root_cause import apply_overlay_policy_flow_to_causes

        apply_overlay_policy_flow_to_causes(causes, ctx.get("overlay_policy_flow"))

    sanitize_root_causes_for_display(causes)

    if joint_done and isinstance(targeted_probe, dict):
        _gate = _joint_overlay_gate_from_cli_context(targeted_probe, cpe_result, topology)
        causes = _filter_business_joint_causes_for_datapath_accuracy(
            causes,
            _gate.overlay_evidence_positive,
            targeted_probe_business_rows_all_ok(targeted_probe),
        )

    sev = _severity_from_causes(
        causes,
        outcome.status,
        business_probe_all_ok=(outcome.status == "ok"),
    )
    if joint_done:
        if joint_needed:
            summary = (
                f"业务探测未通过；已完成 PC+CPE+拓扑联合分析，共 {len(causes)} 条结论。"
                f"{(' 探测侧错误: ' + sanitize_user_visible_text(outcome.aggregate_error)) if outcome.aggregate_error else ''}"
            )
        else:
            summary = (
                f"业务探测已成功；已完成 PC+CPE+拓扑端到端核查报告，共 {len(causes)} 条观察/提示。"
                f"{(' 探测侧提示: ' + sanitize_user_visible_text(outcome.aggregate_error)) if outcome.aggregate_error else ''}"
            )
        dtype = "business_diagnosis_joint"
        confidence = 0.88
    else:
        summary = (
            f"业务探测完成：{len(specs)} 个目标；"
            f"识别 {len(causes)} 条根因线索。"
            f"{(' 探测侧错误: ' + sanitize_user_visible_text(outcome.aggregate_error)) if outcome.aggregate_error else ''}"
        )
        dtype = "business_diagnosis"
        confidence = (
            0.82 if outcome.status == "ok" and collect_pc else (0.68 if collect_pc else 0.58)
        )

    diagnosis = DiagnosisResult(
        trace_id=trace_id,
        diagnosis_type=dtype,
        root_causes=causes,
        severity=sev,
        summary=summary,
        overall_confidence=confidence,
    )

    obs = build_observation_standalone(trace_id, pc_snapshot if collect_pc else None)
    bundle = ProbeBundle(trace_id=trace_id, business_probes=list(outcome.business_probes))
    hypotheses = BusinessRCAEngine().hypotheses(obs, bundle)
    hyp_payload = [
        {"id": h.hypothesis_id, "statement": h.statement, "refs": list(h.evidence_refs)}
        for h in hypotheses
    ]

    fmt_norm = str(fmt).lower()
    if fmt_norm == "json":
        out_path = Path(output) if output else Path("reports") / f"business_diagnosis_{trace_id[:8]}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rp_targets = biz_targets_from_business_probes(list(outcome.business_probes))
        report_pack_json = build_business_diagnose_pack(
            result=diagnosis,
            joint_mode=joint_done,
            biz_targets=rp_targets,
            joint_failure_driven=(joint_needed if joint_done else None),
        ).as_template_dict()
        payload: dict[str, Any] = {
            "trace_id": trace_id,
            "diagnosis": {**outcome.to_json_payload(), "root_causes": [c.to_json_dict() for c in causes]},
            "hypotheses": hyp_payload,
            "pc_snapshot_collected": bool(collect_pc),
            "joint_diagnosis": joint_done,
            "report_pack": report_pack_json,
        }
        opf_json = ctx.get("overlay_policy_flow")
        if isinstance(opf_json, dict):
            payload["overlay_policy_flow"] = opf_json
        if joint_done and isinstance(targeted_probe, dict):
            _jg = _joint_overlay_gate_from_cli_context(targeted_probe, cpe_result, topology)
            payload["declared_business_datapath_verdict"] = (
                "overlay_evidence_positive" if _jg.overlay_evidence_positive else "unverified"
            )
            payload["joint_overlay_rule_case"] = _jg.rule_case
        if joint_done and topology is not None:
            payload["topology"] = topology.to_dict()
        if joint_done and targeted_probe is not None:
            payload["targeted_probe"] = targeted_probe
        if collect_pc and pc_snapshot is not None and hasattr(pc_snapshot, "to_json_dict"):
            payload["pc_snapshot"] = pc_snapshot.to_json_dict()
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON 已写入: {out_path}")
        return

    if output:
        out_path = Path(output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path("./reports")
        out_dir.mkdir(exist_ok=True)
        if joint_done:
            if joint_needed:
                out_path = out_dir / f"business_joint_postfailure_{ts}.html"
            else:
                out_path = out_dir / f"business_joint_verify_{ts}.html"
        else:
            out_path = out_dir / f"business_probe_{ts}.html"

    if joint_done and topology is not None:
        # 联合报告：带 report_html_h1 时由 html_builder 选用 deep_dive_joint_ux.html（原版 deep_dive.html 仍供纯深度诊断）
        cpe_cfg_json = None
        if cpe_result and getattr(cpe_result, "success", False) and isinstance(cpe_result.data, dict):
            cpe_cfg_json = cpe_result.data.get("cpe_configuration")
        top_d_json = topology.to_dict() if topology is not None and hasattr(topology, "to_dict") else None
        underlay_declared_focus = bool(
            isinstance(targeted_probe, dict)
            and not business_joint_should_present_overlay_tunnel_narrative(
                targeted_probe,
                cpe_configuration=cpe_cfg_json,
                topology_dict=top_d_json,
            )
        )
        try:
            html = _write_joint_deep_dive_style_report(
                trace_id=trace_id,
                diagnosis=diagnosis,
                topology=topology,
                cpe_result=cpe_result,
                targeted_probe=targeted_probe,
                pc_snapshot=pc_snapshot if collect_pc else None,
                out_path=out_path,
                joint_failure_driven=joint_needed,
                overlay_policy_flow=ctx.get("overlay_policy_flow"),
                underlay_declared_business_focus=underlay_declared_focus,
                biz_targets=(
                    biz_targets_from_targeted_probe(
                        targeted_probe if isinstance(targeted_probe, dict) else None
                    )
                    or biz_targets_from_business_probes(list(outcome.business_probes))
                ),
            )
            if not output:
                print(f"业务联合 HTML 已保存: {out_path}")
            else:
                print(f"联合分析报告已保存: {out_path} ({len(html)} bytes)")
        except Exception as exc:
            logger.error("联合分析报告生成失败: %s", exc, exc_info=True)
            print(f"报告生成失败: {exc}")
            sys.exit(1)
        return

    # 仅本机探测（未联合 CPE）：HtmlReportBuilder.build_business_diagnosis_report → business_diagnosis.html
    builder = HtmlReportBuilder()
    extra: dict[str, Any] = {
        "aggregate_error": outcome.aggregate_error,
        "probe_status": outcome.status,
        "hypotheses": hyp_payload,
        "confidence_note": (
            "本报告已纳入 PC 观测摘要与探针证据。"
            if collect_pc
            else "未采集 PC 快照：结论仅限 DNS/TCP 探针层，置信度已下调。"
        ),
    }
    opf_probe_only = ctx.get("overlay_policy_flow")
    if isinstance(opf_probe_only, dict) and opf_probe_only.get("data"):
        extra["overlay_policy_flow"] = opf_probe_only
    if collect_pc and pc_snapshot is not None:
        extra["pc_snapshot"] = (
            pc_snapshot.to_json_dict() if hasattr(pc_snapshot, "to_json_dict") else str(pc_snapshot)
        )
    try:
        html = builder.build_business_diagnosis_report(
            diagnosis,
            outcome.business_probes,
            out_path,
            extra_context=extra,
        )
        if not output:
            print(f"报告已保存: {out_path}")
        else:
            print(f"报告已保存: {out_path} ({len(html)} bytes)")
    except Exception as exc:
        logger.error("报告生成失败: %s", exc, exc_info=True)
        print(f"报告生成失败: {exc}")
        sys.exit(1)

