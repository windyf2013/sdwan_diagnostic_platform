"""
深度诊断 CLI 命令 (DeepDive)

提供 PC + CPE 联合诊断功能，支持 SSH/TELNET 连接参数配置。
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

import click

import sdwan_desktop.tools.implementations.network.dns  # noqa: F401 register dns tool
import sdwan_desktop.tools.implementations.network.tcping  # noqa: F401 register tcping tool
import sdwan_desktop.tools.implementations.network.traceroute  # noqa: F401 register traceroute tool

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.flow.definitions.deep_dive import (
    DEEP_DIVE_DEFAULT_BIZ_TARGETS,
    DEEP_DIVE_FLOW,
)
from sdwan_desktop.runtime.engine import FlowRuntime
from sdwan_desktop.services.collector.windows_collector import WindowsCollector
from sdwan_desktop.services.collector.cpe_collector import CpeCollector, CpeCollectorConfig
from sdwan_desktop.services.collector.cpe_credentials_loader import (
    default_cpe_credentials_path,
    load_device_credentials_file,
)
from sdwan_desktop.services.collector.cpe_view_credentials_loader import (
    default_cpe_view_credentials_path,
    load_view_credentials_file,
)
from sdwan_desktop.services.topology.topology_builder import TopologyBuilder
from sdwan_desktop.services.probe.planner import (
    extract_tunnel_peer_ips_from_cpe_configuration,
    plan_post_topology_probe_commands,
)
from sdwan_desktop.services.probe.business_host_probe import (
    BizDomainPortSpec,
    parse_biz_target_tokens,
)
from sdwan_desktop.services.diagnosis.business_diagnosis import (
    orchestrate_business_domain_port_diagnosis,
)
from sdwan_desktop.services.diagnosis.overlay_policy_flow_evidence import (
    run_overlay_policy_flow_step,
)
from sdwan_desktop.services.analyzer.root_cause import RootCauseEngine
from sdwan_desktop.services.reporter.html_builder import HtmlReportBuilder
from sdwan_desktop.services.topology.pc_topology_input import (
    ipv4_same_slash24,
    snapshot_to_topology_input,
)
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, Severity, RootCause

logger = logging.getLogger(__name__)


# 与 ``flow.definitions.deep_dive.DEEP_DIVE_DEFAULT_BIZ_TARGETS`` 同源（CLI 本地别名）。
DEFAULT_BIZ_TARGETS = DEEP_DIVE_DEFAULT_BIZ_TARGETS


def _extract_probe_target_ips(rows: list[dict[str, Any]]) -> list[str]:
    """从业务探测结果提取目标 IP（优先 TCP host，其次 DNS A）。"""
    ips: list[str] = []
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
    dedup: list[str] = []
    seen: set[str] = set()
    for ip in ips:
        if ip and ip not in seen:
            seen.add(ip)
            dedup.append(ip)
    return dedup


def _append_iface_row(bucket: list, iface: str, ip: str) -> None:
    """向接口列表追加一行（去重）。"""
    if not ip:
        return
    iface = iface or "—"
    key = (iface, ip)
    if any((x.get("interface"), x.get("ip")) == key for x in bucket):
        return
    bucket.append({"interface": iface, "ip": ip})


def _underlay_hub_iface_rows(tunnel_edge: Optional[dict]) -> tuple[list, list]:
    """Hub 在 Underlay 横排末端的上下行展示：面向 CPE 出口与隧道外目的/默认下一跳。"""
    if not tunnel_edge:
        return [], []
    tmd = tunnel_edge.get("metadata") or {}
    wan = (tmd.get("underlay_wan_ip") or "").strip()
    nh = (tmd.get("underlay_next_hop_ip") or "").strip()
    remote = (
        (tmd.get("overlay_tunnel_peer_ip") or tunnel_edge.get("target_interface") or "")
        .strip()
    )
    down: list = []
    if wan:
        down.append({"interface": "↔ CPE 出口", "ip": wan})
    up: list = []
    if remote:
        up.append({"interface": "隧道外目的", "ip": remote})
    if nh and nh != remote:
        up.append({"interface": "CPE 默认下一跳", "ip": nh})
    return down, up


def _synthetic_gateway_to_hub_edge(gw_id: str, hub_id: str, tunnel_edge: dict) -> dict:
    """默认路由域末端到隧道对端：无独立拓扑边，仅用于图形区 hop 样式。"""
    tmd = tunnel_edge.get("metadata") or {}
    remote = (
        (tmd.get("overlay_tunnel_peer_ip") or tunnel_edge.get("target_interface") or "")
        .strip()
    )
    return {
        "link_type": "logical",
        "source_id": gw_id,
        "target_id": hub_id,
        "source_interface": (tmd.get("underlay_next_hop_ip") or "").strip() or None,
        "target_interface": remote or None,
        "metadata": {
            "adjacency_evidence": "tunnel_remote_underlay_path",
            "description": "经出口路由域可达的隧道配置对端（非必有二层直连）",
        },
    }


def _hop_connection_style(edge: Optional[dict]) -> str:
    """图形区 hop：physical 视为直连示意，其余为经路由/隧道域过渡。"""
    if not edge:
        return "indirect"
    if edge.get("link_type") == "physical":
        return "direct"
    return "indirect"


def _enrich_topology_report_dict(topo_dict: dict) -> None:
    """为深度报告补充：节点上下行接口、Underlay/Overlay 双平面、链路同前缀说明与 hop 标签。"""
    nodes = topo_dict.get("nodes") or []
    edges = topo_dict.get("edges") or []
    by_id = {n["id"]: n for n in nodes}

    pc_id = topo_dict.get("pc_node_id")
    cpe_id = topo_dict.get("cpe_node_id")
    gw_id = topo_dict.get("gateway_node_id")
    hub_id = topo_dict.get("hub_node_id")

    cpe_hub_tunnel: Optional[dict] = None
    if hub_id and cpe_id:
        cpe_hub_tunnel = next(
            (
                e
                for e in edges
                if e.get("link_type") == "tunnel"
                and e.get("source_id") == cpe_id
                and e.get("target_id") == hub_id
            ),
            None,
        )

    uplink: dict[str, list] = {n["id"]: [] for n in nodes}
    downlink: dict[str, list] = {n["id"]: [] for n in nodes}

    for edge in edges:
        md = edge.get("metadata") or {}
        src, dst = edge.get("source_id"), edge.get("target_id")
        s_ip, t_ip = edge.get("source_interface"), edge.get("target_interface")
        s_nm = md.get("source_interface_name") or ""
        t_nm = md.get("target_interface_name") or ""

        if src and src in uplink and s_ip and edge.get("link_type") != "tunnel":
            _append_iface_row(uplink[src], s_nm, s_ip)
        if dst and dst in downlink and t_ip and edge.get("link_type") != "tunnel":
            _append_iface_row(downlink[dst], t_nm, t_ip)

    under_ids = [x for x in (pc_id, cpe_id, gw_id) if x and x in by_id]
    # 隧道对端 Hub 仅在 Overlay 展示；Underlay 不画「隧道语义」的 Hub 节点（避免与 tracert 公网路径混淆）。
    if (
        hub_id
        and hub_id in by_id
        and hub_id not in under_ids
        and cpe_hub_tunnel is None
    ):
        under_ids.append(hub_id)

    if hub_id and hub_id in downlink and cpe_hub_tunnel:
        hdown, hup = _underlay_hub_iface_rows(cpe_hub_tunnel)
        downlink[hub_id] = hdown
        uplink[hub_id] = hup

    for n in nodes:
        nid = n.get("id")
        meta = n.get("metadata") or {}
        for k in ("ingress_paths", "egress_paths"):
            meta.pop(k, None)
        meta["uplink_interfaces"] = uplink.get(nid, [])
        meta["downlink_interfaces"] = downlink.get(nid, [])
        n["metadata"] = meta

    under_list = [by_id[i] for i in under_ids]
    if not under_list and nodes:
        under_list = list(nodes)
    topo_dict["layout_underlay_nodes"] = under_list

    if hub_id and hub_id in by_id and cpe_id and cpe_id in by_id:
        tunnel_edge = cpe_hub_tunnel
        tmd = (tunnel_edge or {}).get("metadata") or {}
        hub_node = by_id[hub_id]
        seg_ip = (tmd.get("overlay_segment_peer_ip") or "").strip()
        tun_peer = (tmd.get("overlay_tunnel_peer_ip") or hub_node.get("ip_address") or "").strip()
        hub_display_ip = seg_ip or tun_peer
        wan_ip = (tmd.get("underlay_wan_ip") or "").strip()
        nh_ip = (tmd.get("underlay_next_hop_ip") or "").strip()
        outer_same = (
            ipv4_same_slash24(wan_ip, tun_peer) if wan_ip and tun_peer else False
        )
        encap_note = (
            ""
            if outer_same
            else (
                "对端为隧道配置的外层可达地址，常与 CPE 出口地址不同网段；"
                "经默认路由及后续网络转发，与「链路一览」中 Tunnel 段描述一致。"
            )
        )
        cpe_encap_lbl = "封装地址" if outer_same else "本端出口封装"
        hub_encap_lbl = "封装地址" if outer_same else "对端隧道目的"
        topo_dict["layout_overlay"] = {
            "cpe_node": by_id[cpe_id],
            "hub_node": hub_node,
            "overlay_local_iface": tmd.get("overlay_local_iface", ""),
            "overlay_local_ip": tmd.get("overlay_local_ip", ""),
            "overlay_segment_peer_ip": seg_ip,
            "hub_overlay_display_ip": hub_display_ip,
            "hub_encap_peer_ip": tun_peer if tun_peer and tun_peer != hub_display_ip else "",
            "cpe_encap_local_iface": tmd.get("underlay_wan_iface", ""),
            "cpe_encap_local_ip": tmd.get("underlay_wan_ip", ""),
            "hub_tunnel_ip": seg_ip or hub_display_ip,
            "hub_encap_ip": tun_peer or hub_display_ip,
            "overlay_outer_encap_same_slash24": outer_same,
            "overlay_underlay_next_hop_ip": nh_ip,
            "cpe_encap_row_label": cpe_encap_lbl,
            "hub_encap_row_label": hub_encap_lbl,
            "overlay_encap_note": encap_note,
        }
        topo_dict["layout_overlay_placeholder"] = ""
    else:
        topo_dict["layout_overlay"] = None
        topo_dict["layout_overlay_placeholder"] = (
            "当前无可用 Overlay（无活性隧道或未解析到 Hub）；仅展示 Underlay。"
        )

    for edge in edges:
        md = edge.get("metadata") or {}
        lt = edge.get("link_type")
        if lt == "physical":
            ok = md.get("same_subnet_slash24")
            edge["report_same_subnet"] = bool(ok)
            evid = md.get("adjacency_evidence") or ""
            evid_suffix = ""
            if evid == "cpe_arp_gateway":
                evid_suffix = "（CPE ARP 已解析下一跳）"
            elif evid == "explicit_subnet_route":
                evid_suffix = "（出接口显式前缀 ≥/24）"
            elif evid == "slash24_heuristic":
                evid_suffix = "（无 ARP/显式前缀，仅靠同源 /24 推断）"
            edge["report_subnet_note"] = (
                f"同源 /24 推断邻接 ✅{evid_suffix}" if ok else f"⚠ 未发现同源 /24{evid_suffix} — 核对实际二层或多跳路由"
            )
        elif lt == "logical":
            ev = md.get("adjacency_evidence") or ""
            if ev == "session_reachable":
                edge["report_same_subnet"] = bool(md.get("same_subnet_slash24"))
                edge["report_subnet_note"] = (
                    "流程内信息采集成功 ⇒ 本机与 CPE 管理地址会话可达。"
                    + (
                        " PC 主地址与管理地址同属 /24（推断）。"
                        if md.get("same_subnet_slash24")
                        else " PC 主地址与管理地址跨 /24（推断）。"
                    )
                    + " 不表示已通过 ARP/MAC 证明二层同 LAN。"
                )
            else:
                edge["report_same_subnet"] = False
                edge["report_subnet_note"] = str(
                    md.get("subnet_alignment_note")
                    or "仅默认路由语义，下一跳是否与出接口同属一网段请结合 ARP / 前缀核对。"
                )
        elif lt == "tunnel":
            edge["report_underlay_ok"] = bool(md.get("underlay_same_subnet"))
            edge["report_overlay_segment_ok"] = bool(md.get("overlay_segment_same_subnet"))
            edge["report_subnet_note"] = (
                "Underlay（WAN↔下一跳）与 Overlay（vxlan 段内邻接）均已按 /24 校验"
                if edge["report_underlay_ok"] and edge["report_overlay_segment_ok"]
                else "请核对 Underlay 与 Overlay 段内地址对；隧道对端可能仅为 /32 主机路由"
            )

    directed: dict[tuple[str, str], dict] = {}
    for edge in edges:
        s = edge.get("source_id")
        d = edge.get("target_id")
        if isinstance(s, str) and isinstance(d, str):
            directed[(s, d)] = edge

    layout_underlay_items: list[dict] = []
    if under_ids:
        for idx, nid in enumerate(under_ids):
            layout_underlay_items.append({"kind": "node", "node": by_id[nid]})
            if idx + 1 >= len(under_ids):
                break
            nxt_id = under_ids[idx + 1]
            bridging = directed.get((nid, nxt_id))
            if (
                bridging is None
                and cpe_hub_tunnel
                and gw_id
                and nid == gw_id
                and nxt_id == hub_id
            ):
                bridging = _synthetic_gateway_to_hub_edge(gw_id, hub_id, cpe_hub_tunnel)
            layout_underlay_items.append(
                {
                    "kind": "hop",
                    "connection": _hop_connection_style(bridging),
                    "source_id": nid,
                    "target_id": nxt_id,
                    "edge_key": f"{nid}->{nxt_id}",
                }
            )
    elif under_list:
        layout_underlay_items = [{"kind": "node", "node": nn} for nn in under_list]
    topo_dict["layout_underlay_items"] = layout_underlay_items


@click.command(
    epilog=(
        "定位: 运维侧 CPE 配置与运行态专检，叠加本机对 baidu/youtube/tiktok 的链路分流探测。\n"
        "默认业务目标: 省略 -b 时自动注入 www.baidu.com:443 / www.youtube.com:443 / www.tiktok.com:443，\n"
        "  PC 侧执行 DNS(A)+TCP+traceroute（即「链路分流」证据）；不做「DNS 分流」对照——\n"
        "  仅当显式传入 --biz-dns-server 时才以自定义 DNS 与系统解析对比。\n"
        "不包含: 不等价于仅本机 quick-check；默认非单业务 SLA 交付包（请用 business-diagnose）。\n"
        "升级: 终端自助 → quick-check；单业务路径 → business-diagnose。\n"
        "报告 HTML 含「报告定位」扉页；联合证据见拓扑后探测区块。"
    ),
)
@click.option(
    '--cpe-host',
    '--cpe',
    '-c',
    'cpe',
    required=True,
    metavar='IP',
    help='CPE 管理面 IP（推荐长选项 --cpe-host；与 --cpe、-c 等价）。',
)
@click.option('--port', '-p', default=23, help='连接端口（默认 23，Telnet 常用）。')
@click.option(
    '--username',
    '--user',
    '-u',
    'user',
    required=True,
    metavar='NAME',
    help='登录用户名（推荐 --username；与 --user、-u 等价）。',
)
@click.option(
    '--password',
    default=None,
    help='登录密码（或使用 --key-file / -k 私钥）。',
)
@click.option('--key-file', '-k', default=None, help='SSH 私钥文件路径。')
@click.option(
    '--protocol',
    '-P',
    default='telnet',
    type=click.Choice(['telnet', 'ssh'], case_sensitive=False),
    help='连接协议：telnet 或 ssh（默认 telnet）。短选项 -P 为大写，与 -p 端口区分。',
)
@click.option('--output', '-o', default=None, help='报告输出 HTML 路径。')
@click.option(
    '--credentials-file',
    '-f',
    type=click.Path(exists=False, path_type=Path, dir_okay=False),
    default=None,
    help='CPE 凭证 YAML；-f 为短名。未指定且存在 configs/cpe_credentials.yaml 时自动读取。',
)
@click.option(
    '--view-credentials-file',
    '-V',
    type=click.Path(exists=False, path_type=Path, dir_okay=False),
    default=None,
    help='固定视图通用口令 YAML；-V 为短名。未指定且存在 configs/cpe_view_credentials.yaml 时自动读取。',
)
@click.option('--verbose', '-v', is_flag=True, help='详细日志。')
@click.option(
    '--biz-target',
    '-b',
    multiple=True,
    help=(
        '业务探测：FQDN:TCP端口，可多次；-b 与每次取值等价。省略端口时默认 443；'
        '在 PC 侧做 DNS(A)+TCP+可选 traceroute（链路分流证据）。'
        '完全省略 -b 时按默认 baidu/youtube/tiktok 三个目标执行（端口 443）。'
    ),
)
@click.option(
    '--biz-dns-server',
    '-S',
    default=None,
    metavar='IPV4',
    help='业务 DNS 解析使用的服务器 IPv4（可选；-S 为短名；默认系统解析）。',
)
@click.option(
    '--no-traceroute',
    is_flag=True,
    default=False,
    help='业务探测时跳过本机 traceroute（默认对解析 IPv4 执行路径追踪作旁证）。',
)
def deep_dive(
    cpe: str,
    port: int,
    user: str,
    password: Optional[str],
    key_file: Optional[str],
    protocol: str,
    output: Optional[str],
    credentials_file: Optional[Path],
    view_credentials_file: Optional[Path],
    verbose: bool,
    biz_target: Tuple[str, ...],
    biz_dns_server: Optional[str],
    no_traceroute: bool,
):
    """执行 SD-WAN 深度诊断 (PC + CPE 联合分析)"""
    from sdwan_desktop.flow.handlers.deep_dive_steps import (
        DeepDiveHandlersParams,
        run_deep_dive_flow,
    )

    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    biz_target_tokens: Tuple[str, ...] = biz_target if biz_target else DEFAULT_BIZ_TARGETS
    if output:
        out_path = Path(output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path("./reports")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"deep_dive_{ts}.html"

    run_params = DeepDiveHandlersParams(
        cpe_host=cpe,
        username=user,
        cpe_port=port,
        password=password,
        key_file=key_file,
        protocol=protocol,
        output_path=out_path,
        credentials_file=credentials_file,
        view_credentials_file=view_credentials_file,
        biz_targets=biz_target_tokens,
        biz_dns_server=biz_dns_server,
        no_traceroute=no_traceroute,
        verbose=verbose,
        console=True,
    )

    try:
        asyncio.run(run_deep_dive_flow(run_params))
    except Exception as exc:
        logger.error("深度诊断执行失败: %s", exc, exc_info=True)
        print(f"\n执行失败: {exc}")
        sys.exit(1)
