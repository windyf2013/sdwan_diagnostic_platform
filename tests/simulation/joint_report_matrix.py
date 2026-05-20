"""业务联合报告：多组网 / 多故障仿真矩阵（HTML 目视验收）。

生成至 ``reports/sim_matrix/``；运行::

    python scripts/generate_joint_report_matrix.py

或::

    pytest tests/simulation/test_joint_report_visual_matrix.py -v
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sdwan_desktop.core.types.cpe_config import (
    CpeConfiguration,
    InterfaceInfo,
    SdwanPolicy,
    VpnTunnelInfo,
)
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.topology.topology import Edge, LinkType, NetworkTopology, Node, NodeType

# 项目根：tests/simulation -> tests -> platform
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUT = _REPO_ROOT / "reports" / "sim_matrix"


@dataclass(frozen=True, slots=True)
class JointReportScenario:
    """单场景仿真定义。"""

    scenario_id: str
    title: str
    description: str
    joint_failure_driven: bool
    domain: str
    biz_ip: str
    build_targeted_probe: Callable[[], dict]
    build_cpe: Callable[[], CpeConfiguration]
    build_topology: Callable[[], NetworkTopology]
    root_causes: tuple[RootCause, ...] = ()
    expected_rule_case: str = ""
    expected_show_overlay: bool = False
    expected_evidence_tier: str = "underlay_only"
    expected_config_intent: str = ""
    expected_reconcile_outcome: str = ""
    expected_break_point: str = ""
    expected_s1_status: str = ""
    tags: tuple[str, ...] = ()


def _trace_hops(ips: List[str]) -> List[dict]:
    return [{"hop": i + 1, "ip": ip, "rtts": [1.0, 1.0, 1.0]} for i, ip in enumerate(ips)]


def _tp_base(
    *,
    domain: str,
    biz_ip: str,
    conntrack_line: str,
    dns_ok: bool = True,
    tcp_ok: bool = True,
    trace_ips: Optional[List[str]] = None,
    extra_raw: Optional[Dict[str, str]] = None,
) -> dict:
    row: dict = {
        "domain": domain,
        "port": 443,
        "dns": {
            "status": "ok" if dns_ok else "error",
            "data": {"resolved_ips": [biz_ip]},
        },
    }
    if tcp_ok:
        row["tcp"] = [
            {
                "host": biz_ip,
                "port": 443,
                "status": "ok",
                "data": {"port_open": True},
            }
        ]
    else:
        row["tcp"] = [
            {
                "host": biz_ip,
                "port": 443,
                "status": "error",
                "error": "[TOOL_TIMEOUT] tcping timeout",
            }
        ]
    if trace_ips:
        row["trace"] = [
            {
                "host": biz_ip,
                "port": 443,
                "status": "ok",
                "data": {
                    "summary": {"target_reached": False, "total_hops": len(trace_ips)},
                    "hops": _trace_hops(trace_ips),
                },
            }
        ]
    raw: Dict[str, str] = {
        f"diagnose:nf_conntrack grep {biz_ip}": conntrack_line,
        "diagnose:ping tunnel_peer 5.96.1.26": "2 packets transmitted, 2 received, 0% packet loss",
        "diagnose:ping tunnel_peer 5.100.1.18": "2 packets transmitted, 2 received, 0% packet loss",
    }
    if extra_raw:
        raw.update(extra_raw)
    return {
        "status": "ok" if dns_ok else "partial",
        "data": {
            "business_probes": [row],
            "biz_target_ips": [biz_ip],
            "raw_outputs": raw,
        },
        "error": None,
    }


def _cpe_with_url_group_domain(
    *,
    domain: str,
    group: str = "acceleratePlus",
    pc_security_ip: str = "192.168.54.17",
    security_enabled: bool = True,
    interfaces: Optional[List[InterfaceInfo]] = None,
    extra_raw: Optional[Dict[str, str]] = None,
) -> CpeConfiguration:
    """5200B CPE + url-group running-config / domain / security-ip 原始输出。"""
    sec_line = " security ip enable\n" if security_enabled else ""
    cpe = _raisecom_cpe(
        policies=[SdwanPolicy(name="acc", source="192.168.54.0/24")],
        interfaces=interfaces,
    )
    raw: Dict[str, str] = {
        "show running-config": f"url-group {group}\n{sec_line} priority 100\nexit\n",
        "show url-group all security-ip": f"url-group {group}\n{pc_security_ip}\n",
        "show url-group all domain all": f"url-group {group}\n{domain}\nexit\n",
    }
    if extra_raw:
        raw.update(extra_raw)
    cpe.raw_outputs = raw
    return cpe


def _raisecom_cpe(
    *,
    policies: Optional[List[SdwanPolicy]] = None,
    interfaces: Optional[List[InterfaceInfo]] = None,
) -> CpeConfiguration:
    ifaces = interfaces or [
        InterfaceInfo(name="ge1", ip_address="192.168.20.20", status="up"),
    ]
    return CpeConfiguration(
        vendor="raisecom",
        model="MSG5200B",
        version="1.0",
        hostname="cpe-sim",
        interfaces=ifaces,
        sdwan_policies=policies or [],
        vpn_tunnels=[
            VpnTunnelInfo(remote_ip="5.96.1.26", state="up", type="vxlan"),
            VpnTunnelInfo(remote_ip="5.100.1.18", state="up", type="vxlan"),
        ],
    )


def _cisco_cpe() -> CpeConfiguration:
    return CpeConfiguration(
        vendor="cisco",
        model="vedge",
        version="20.9",
        hostname="cpe-cisco",
        vpn_tunnels=[VpnTunnelInfo(remote_ip="5.96.1.26", state="up", type="ipsec")],
    )


def _standard_topology(*, pc_ip: str = "192.168.54.10") -> NetworkTopology:
    t = NetworkTopology()
    t.add_node(
        Node(
            id="pc-1",
            name="PC-SIM",
            node_type=NodeType.PC,
            ip_address=pc_ip,
        )
    )
    t.add_node(
        Node(
            id="cpe-1",
            name="CPE-5200B",
            node_type=NodeType.CPE,
            ip_address="10.10.25.1",
            vendor="raisecom",
            model="MSG5200B",
        )
    )
    t.add_node(
        Node(
            id="gw-1",
            name="WAN-GW",
            node_type=NodeType.GATEWAY,
            ip_address="8.1.3.1",
        )
    )
    t.add_node(
        Node(
            id="hub-1",
            name="POP-Hub",
            node_type=NodeType.HUB,
            ip_address="5.96.1.1",
        )
    )
    t.add_edge(
        Edge(
            id="e-pc-cpe",
            source_id="pc-1",
            target_id="cpe-1",
            link_type=LinkType.LOGICAL,
            source_interface=pc_ip,
            target_interface="10.10.25.1",
        )
    )
    t.add_edge(
        Edge(
            id="e-cpe-gw",
            source_id="cpe-1",
            target_id="gw-1",
            link_type=LinkType.PHYSICAL,
            metadata={"source_interface_name": "ge1"},
        )
    )
    t.add_edge(
        Edge(
            id="e-cpe-hub",
            source_id="cpe-1",
            target_id="hub-1",
            link_type=LinkType.TUNNEL,
            metadata={
                "underlay_wan_iface": "ge1",
                "underlay_wan_ip": "192.168.20.20",
                "underlay_next_hop_ip": "8.1.3.1",
                "overlay_local_iface": "vxlan2500133",
                "overlay_local_ip": "5.96.1.26",
                "overlay_segment_peer_ip": "5.96.1.27",
                "overlay_tunnel_peer_ip": "5.96.1.26",
            },
        )
    )
    return t


_URL_GROUP_MULTI = """url-group acceleratePlus
youtube.com
google.com
!
url-group liveBroadcast
tiktok.com
youtube.com
!
"""


def all_scenarios() -> List[JointReportScenario]:
    """仿真场景清单（组网 × 门控 × 故障）。"""
    return [
        JointReportScenario(
            scenario_id="01_verify_public_d0_youtube",
            title="核查通过 · 公网 Underlay（无 vxlan 回程）",
            description="本机探测通过；conntrack 仅单向公网 DIP、无 vxlan 回程，不展示 Overlay。",
            joint_failure_driven=False,
            domain="youtube.com",
            biz_ip="142.250.185.78",
            build_targeted_probe=lambda: _tp_base(
                domain="youtube.com",
                biz_ip="142.250.185.78",
                conntrack_line=(
                    "tcp ESTABLISHED src=10.10.25.3 dst=142.250.185.78 sport=1 dport=443"
                ),
                trace_ips=[
                    "10.10.100.161",
                    "10.10.25.1",
                    "8.1.3.1",
                    "142.250.185.78",
                ],
            ),
            build_cpe=lambda: _raisecom_cpe(
                policies=[SdwanPolicy(name="acc", source="192.168.54.0/24")]
            ),
            build_topology=lambda: _standard_topology(pc_ip="10.10.100.161"),
            expected_rule_case="raisecom_underlay_no_overlay_evidence",
            expected_show_overlay=False,
            expected_evidence_tier="underlay_only",
            tags=("verify", "underlay", "5200b"),
        ),
        JointReportScenario(
            scenario_id="02_verify_public_d0_baidu",
            title="核查通过 · baidu 公网（无 vxlan 回程）",
            description="与现网 baidu 核查样例同类：有会话、走 main/ge1，不叠加 Overlay。",
            joint_failure_driven=False,
            domain="baidu.com",
            biz_ip="110.242.68.66",
            build_targeted_probe=lambda: _tp_base(
                domain="baidu.com",
                biz_ip="110.242.68.66",
                conntrack_line=(
                    "tcp ESTABLISHED src=10.10.25.3 dst=110.242.68.66 sport=2 dport=443"
                ),
                trace_ips=["10.10.100.161", "10.10.25.1", "61.8.196.147", "110.242.68.66"],
            ),
            build_cpe=_raisecom_cpe,
            build_topology=_standard_topology,
            expected_rule_case="raisecom_underlay_no_overlay_evidence",
            expected_show_overlay=False,
            tags=("verify", "underlay", "5200b"),
        ),
        JointReportScenario(
            scenario_id="03_verify_tunnel_d2_precise",
            title="核查通过 · 全 DIP 隧道（D2 精确定位）",
            description="PC 未匹配策略源，但 conntrack 目的均为隧道下一跳 → 一定走隧道，展示 Overlay。",
            joint_failure_driven=False,
            domain="youtube.com",
            biz_ip="142.250.185.78",
            build_targeted_probe=lambda: _tp_base(
                domain="youtube.com",
                biz_ip="142.250.185.78",
                conntrack_line=(
                    "tcp ESTABLISHED src=10.0.0.5 dst=5.96.1.26 sport=1 dport=443"
                ),
            ),
            build_cpe=lambda: _raisecom_cpe(
                policies=[SdwanPolicy(name="acc", source="192.168.54.0/24")]
            ),
            build_topology=lambda: _standard_topology(pc_ip="10.0.0.5"),
            expected_rule_case="raisecom_all_dip_tunnel_precise",
            expected_show_overlay=True,
            expected_evidence_tier="precise",
            tags=("verify", "d2", "5200b", "overlay"),
        ),
        JointReportScenario(
            scenario_id="04_verify_policy_d1",
            title="核查通过 · 策略源匹配（D1）",
            description="PC 在策略源前缀内 + 会话 DIP 为隧道地址 → 精确定位，展示 Overlay。",
            joint_failure_driven=False,
            domain="youtube.com",
            biz_ip="142.250.185.78",
            build_targeted_probe=lambda: _tp_base(
                domain="youtube.com",
                biz_ip="142.250.185.78",
                conntrack_line=(
                    "tcp ESTABLISHED src=192.168.54.17 dst=5.96.1.26 sport=1 dport=443"
                ),
            ),
            build_cpe=lambda: _raisecom_cpe(
                policies=[SdwanPolicy(name="acc", source="192.168.54.0/24")]
            ),
            build_topology=lambda: _standard_topology(pc_ip="192.168.54.17"),
            expected_rule_case="raisecom_session_matched_policy_prefix",
            expected_show_overlay=True,
            expected_evidence_tier="precise",
            tags=("verify", "d1", "5200b", "overlay"),
        ),
        JointReportScenario(
            scenario_id="05_postfailure_tcp_public",
            title="探测失败 · TCP 超时 + 公网 conntrack（Underlay）",
            description="联合诊断模式；业务 TCP 失败，路径旁证出 CPE，不展示 Overlay 条带。",
            joint_failure_driven=True,
            domain="www.tiktok.com",
            biz_ip="31.13.92.37",
            build_targeted_probe=lambda: _tp_base(
                domain="www.tiktok.com",
                biz_ip="31.13.92.37",
                conntrack_line=(
                    "ipv4 2 tcp 6 0 SYN_SENT src=10.10.25.3 dst=31.13.92.37 "
                    "sport=1 dport=443 [UNREPLIED]"
                ),
                tcp_ok=False,
                trace_ips=[
                    "10.10.100.161",
                    "10.10.25.1",
                    "8.1.3.1",
                    "5.1.1.2",
                    "61.8.196.147",
                ],
            ),
            build_cpe=_raisecom_cpe,
            build_topology=_standard_topology,
            root_causes=(
                RootCause(
                    cause_id="BIZ-TCP",
                    title="业务 TCP 建连失败",
                    description="声明目标端口不可达或超时。",
                    severity=Severity.CRITICAL,
                    confidence=0.85,
                ),
            ),
            expected_rule_case="raisecom_underlay_no_overlay_evidence",
            expected_show_overlay=False,
            tags=("postfailure", "underlay", "5200b"),
        ),
        JointReportScenario(
            scenario_id="06_heuristic_d3_trace_overlay",
            title="启发式 · 跳表命中 Overlay（D3）",
            description="混合 DIP；traceroute 经隧道地址 → 【启发式】展示 Overlay。",
            joint_failure_driven=False,
            domain="youtube.com",
            biz_ip="142.250.185.78",
            build_targeted_probe=lambda: _tp_base(
                domain="youtube.com",
                biz_ip="142.250.185.78",
                conntrack_line=(
                    "tcp ESTABLISHED src=10.0.0.5 dst=142.250.185.78 sport=1 dport=443 "
                    "tcp ESTABLISHED src=10.0.0.5 dst=5.96.1.26 sport=2 dport=443"
                ),
                trace_ips=[
                    "10.10.100.161",
                    "10.10.25.1",
                    "5.96.1.26",
                    "142.250.185.78",
                ],
            ),
            build_cpe=_raisecom_cpe,
            build_topology=lambda: _standard_topology(pc_ip="10.0.0.5"),
            expected_rule_case="raisecom_trace_overlay_hop",
            expected_show_overlay=True,
            expected_evidence_tier="heuristic",
            tags=("verify", "d3", "heuristic", "overlay"),
        ),
        JointReportScenario(
            scenario_id="07_no_conntrack",
            title="无会话采样",
            description="nf_conntrack 无有效行；不展示 Overlay，页首说明会话不匹配。",
            joint_failure_driven=False,
            domain="svc.internal",
            biz_ip="203.0.113.50",
            build_targeted_probe=lambda: _tp_base(
                domain="svc.internal",
                biz_ip="203.0.113.50",
                conntrack_line="",
            ),
            build_cpe=_raisecom_cpe,
            build_topology=_standard_topology,
            expected_rule_case="raisecom_no_conntrack_sampling",
            expected_show_overlay=False,
            tags=("verify", "no_ct", "5200b"),
        ),
        JointReportScenario(
            scenario_id="08_url_group_multi_tiktok",
            title="url-group 多组优先级（D5 补充）",
            description="tiktok 属两组；生效组 liveBroadcast；叙述写入路径实证（不单独开 Overlay）。",
            joint_failure_driven=False,
            domain="tiktok.com",
            biz_ip="31.13.92.37",
            build_targeted_probe=lambda: _tp_base(
                domain="tiktok.com",
                biz_ip="31.13.92.37",
                conntrack_line=(
                    "tcp ESTABLISHED src=10.10.25.3 dst=31.13.92.37 sport=1 dport=443"
                ),
                extra_raw={"show url-group all domain all": _URL_GROUP_MULTI},
            ),
            build_cpe=_raisecom_cpe,
            build_topology=_standard_topology,
            expected_rule_case="raisecom_underlay_no_overlay_evidence",
            expected_show_overlay=False,
            tags=("d5", "url-group", "5200b"),
        ),
        JointReportScenario(
            scenario_id="11_replay_193136_vxlan",
            title="回放 193136 · NAT + vxlan 回程",
            description="正向 dst=业务公网 IP，回程 dst=vxlan5 口 → L1 精确定位，展示 Overlay。",
            joint_failure_driven=False,
            domain="youtube.com",
            biz_ip="172.253.118.91",
            build_targeted_probe=lambda: _tp_base(
                domain="youtube.com",
                biz_ip="172.253.118.91",
                conntrack_line=(
                    "tcp TIME_WAIT src=10.10.25.3 dst=172.253.118.91 sport=59974 dport=443 "
                    "src=172.253.118.91 dst=8.1.3.2 sport=443 dport=59974"
                ),
            ),
            build_cpe=lambda: _raisecom_cpe(
                interfaces=[InterfaceInfo(name="vxlan5", ip_address="8.1.3.2")],
                policies=[SdwanPolicy(name="acc", source="192.168.54.0/24")],
            ),
            build_topology=lambda: _standard_topology(pc_ip="10.10.100.161"),
            expected_rule_case="raisecom_overlay_conntrack_bidirectional",
            expected_show_overlay=True,
            expected_evidence_tier="precise",
            tags=("verify", "193136", "l1", "overlay", "5200b"),
        ),
        JointReportScenario(
            scenario_id="09_non_raisecom_ct_only",
            title="非 5200B · 仅 conntrack",
            description="Cisco CPE：有会话但无跳表 Overlay → 不展示隧道条带。",
            joint_failure_driven=False,
            domain="app.example",
            biz_ip="198.51.100.10",
            build_targeted_probe=lambda: _tp_base(
                domain="app.example",
                biz_ip="198.51.100.10",
                conntrack_line=(
                    "tcp SYN_SENT src=10.1.1.5 dst=198.51.100.10 sport=1 dport=443"
                ),
            ),
            build_cpe=_cisco_cpe,
            build_topology=_standard_topology,
            expected_rule_case="non_raisecom_no_overlay_evidence",
            expected_show_overlay=False,
            tags=("cisco", "generic"),
        ),
        JointReportScenario(
            scenario_id="10_non_raisecom_trace_overlay",
            title="非 5200B · 跳表命中隧道",
            description="Cisco + traceroute 经 5.96.1.26 → 启发式展示 Overlay。",
            joint_failure_driven=False,
            domain="app.example",
            biz_ip="198.51.100.10",
            build_targeted_probe=lambda: _tp_base(
                domain="app.example",
                biz_ip="198.51.100.10",
                conntrack_line="",
                trace_ips=["10.10.100.161", "10.10.25.1", "5.96.1.26", "198.51.100.10"],
            ),
            build_cpe=_cisco_cpe,
            build_topology=_standard_topology,
            expected_rule_case="non_raisecom_trace_overlay_hop",
            expected_show_overlay=True,
            expected_evidence_tier="heuristic",
            tags=("cisco", "generic", "overlay"),
        ),
        JointReportScenario(
            scenario_id="12_path_internet_intent",
            title="路径对账 · 未入 url-group（互联网意图）",
            description="声明域不在 url-group 列表；config_intent=internet_underlay。",
            joint_failure_driven=False,
            domain="plain.example",
            biz_ip="203.0.113.20",
            build_targeted_probe=lambda: _tp_base(
                domain="plain.example",
                biz_ip="203.0.113.20",
                conntrack_line=(
                    "tcp ESTABLISHED src=10.10.25.3 dst=203.0.113.20 sport=1 dport=443"
                ),
                extra_raw={
                    "show url-group all domain all": (
                        "url-group acceleratePlus\nother.example\nexit\n"
                    ),
                },
            ),
            build_cpe=lambda: _cpe_with_url_group_domain(
                domain="other.example",
                group="acceleratePlus",
            ),
            build_topology=lambda: _standard_topology(pc_ip="10.10.100.161"),
            expected_rule_case="raisecom_underlay_no_overlay_evidence",
            expected_show_overlay=False,
            expected_config_intent="internet_underlay",
            expected_reconcile_outcome="match",
            tags=("path_matrix", "5200b", "internet"),
        ),
        JointReportScenario(
            scenario_id="13_path_security_miss",
            title="路径对账 · security-ip 未命中",
            description="域在 acceleratePlus 但 PC 不在 security-ip → mismatch。",
            joint_failure_driven=False,
            domain="biz.example",
            biz_ip="203.0.113.10",
            build_targeted_probe=lambda: _tp_base(
                domain="biz.example",
                biz_ip="203.0.113.10",
                conntrack_line=(
                    "tcp ESTABLISHED src=10.10.25.3 dst=203.0.113.10 sport=1 dport=443"
                ),
                extra_raw={
                    "show url-group all domain all": (
                        "url-group acceleratePlus\nbiz.example\nexit\n"
                    ),
                    "diagnose:ipset --list": "Members:\n203.0.113.10 timeout 0\n",
                },
            ),
            build_cpe=lambda: _cpe_with_url_group_domain(
                domain="biz.example",
                pc_security_ip="192.168.54.1",
            ),
            build_topology=lambda: _standard_topology(pc_ip="10.0.0.5"),
            expected_rule_case="raisecom_underlay_no_overlay_evidence",
            expected_show_overlay=False,
            expected_config_intent="sdwan_overlay",
            expected_reconcile_outcome="mismatch",
            expected_break_point="source_not_in_url_group_security_ip",
            tags=("path_matrix", "5200b", "security"),
        ),
        JointReportScenario(
            scenario_id="14_path_link_protect_down",
            title="路径对账 · link-protect / vxlan down",
            description="SD-WAN 意图但保护组动作口 down → overlay_iface 断点。",
            joint_failure_driven=False,
            domain="biz.example",
            biz_ip="203.0.113.11",
            build_targeted_probe=lambda: _tp_base(
                domain="biz.example",
                biz_ip="203.0.113.11",
                conntrack_line="",
                extra_raw={
                    "show url-group all domain all": (
                        "url-group acceleratePlus\nbiz.example\nexit\n"
                    ),
                    "diagnose:ipset --list": "Members:\n203.0.113.11\n",
                    "show link-protect status": (
                        "protect group vxlan2500133 :\n"
                        "  current action link   : vxlan2500133\n"
                        "  current action status : down\n"
                    ),
                },
            ),
            build_cpe=lambda: _cpe_with_url_group_domain(
                domain="biz.example",
                interfaces=[
                    InterfaceInfo(name="vxlan2500133", status="down"),
                    InterfaceInfo(name="ge1", ip_address="192.168.20.20", status="up"),
                ],
            ),
            build_topology=lambda: _standard_topology(pc_ip="192.168.54.17"),
            expected_rule_case="raisecom_no_conntrack_sampling",
            expected_show_overlay=False,
            expected_config_intent="sdwan_overlay",
            expected_reconcile_outcome="mismatch",
            expected_break_point="overlay_iface_down_link_protect",
            tags=("path_matrix", "5200b", "l4"),
        ),
        JointReportScenario(
            scenario_id="15_path_s1_no_ct_sampling",
            title="可达性 S1 · 无 conntrack 采样",
            description="本机探测 OK 但无 ct → S1=no_conntrack_sampling。",
            joint_failure_driven=False,
            domain="svc.example",
            biz_ip="203.0.113.55",
            build_targeted_probe=lambda: _tp_base(
                domain="svc.example",
                biz_ip="203.0.113.55",
                conntrack_line="",
                extra_raw={
                    "show url-group all domain all": (
                        "url-group acceleratePlus\nsvc.example\nexit\n"
                    ),
                },
            ),
            build_cpe=lambda: _cpe_with_url_group_domain(domain="svc.example"),
            build_topology=lambda: _standard_topology(pc_ip="192.168.54.17"),
            expected_rule_case="raisecom_no_conntrack_sampling",
            expected_show_overlay=False,
            expected_config_intent="sdwan_overlay",
            expected_s1_status="no_conntrack_sampling",
            tags=("path_matrix", "5200b", "s1"),
        ),
    ]


@dataclass
class GeneratedScenarioReport:
    scenario_id: str
    html_path: Path
    rule_case: str
    evidence_tier: str
    show_overlay: bool
    suppress_overlay: bool
    banner_snippet: str
    path_config_intent: str = ""
    path_reconcile_outcome: str = ""
    path_break_point: str = ""
    checks: Dict[str, bool] = field(default_factory=dict)


def _path_matrix_checks(
    scenario: JointReportScenario,
    targeted_probe: dict,
    cpe: CpeConfiguration,
    topology: NetworkTopology,
) -> tuple[Dict[str, bool], str, str, str]:
    """Phase E：声明路径对账契约校验（仅 ``path_matrix`` 场景）。"""
    if "path_matrix" not in scenario.tags:
        return {}, "", "", ""
    from sdwan_desktop.services.diagnosis.raisecom_msg5200b_declared_path_analysis import (
        analyze_raisecom_msg5200b_declared_business_path,
    )

    topo_dict = topology.to_dict()
    topo_dict.setdefault("pc_node_id", "pc-1")
    analysis = analyze_raisecom_msg5200b_declared_business_path(
        targeted_probe, cpe, topo_dict
    )
    checks: Dict[str, bool] = {
        "path_analysis_ok": analysis.status == "ok",
        "path_block_expected": True,
    }
    if scenario.expected_config_intent:
        checks["path_config_intent"] = (
            analysis.config_intent == scenario.expected_config_intent
        )
    if scenario.expected_reconcile_outcome:
        checks["path_reconcile_outcome"] = (
            analysis.reconcile.outcome == scenario.expected_reconcile_outcome
        )
    if scenario.expected_break_point:
        checks["path_break_point"] = (
            analysis.reconcile.break_point == scenario.expected_break_point
        )
    if scenario.expected_s1_status:
        checks["path_s1_status"] = (
            analysis.reachability.s1_status == scenario.expected_s1_status
        )
    bp = analysis.reconcile.break_point or ""
    return (
        checks,
        analysis.config_intent,
        analysis.reconcile.outcome,
        bp,
    )


def generate_scenario_html(
    scenario: JointReportScenario,
    out_dir: Path,
) -> GeneratedScenarioReport:
    from sdwan_desktop.interface.cli.commands.business_diagnose import (
        _write_joint_deep_dive_style_report,
    )
    from sdwan_desktop.services.diagnosis.joint_overlay_datapath_gate import (
        compute_joint_overlay_datapath_gate,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scenario.scenario_id}.html"

    diagnosis = DiagnosisResult(
        diagnosis_type="business_diagnose",
        root_causes=list(scenario.root_causes),
    )
    topology = scenario.build_topology()
    cpe = scenario.build_cpe()
    tp = scenario.build_targeted_probe()
    cpe_result = CollectorResult(success=True, data={"cpe_configuration": cpe})

    _write_joint_deep_dive_style_report(
        trace_id=f"sim-{scenario.scenario_id}",
        diagnosis=diagnosis,
        topology=topology,
        cpe_result=cpe_result,
        targeted_probe=tp,
        pc_snapshot=None,
        out_path=out_path,
        joint_failure_driven=scenario.joint_failure_driven,
        biz_targets=[scenario.domain],
    )

    # 读回门控（与 HTML 同源）
    topo_dict = topology.to_dict()
    from sdwan_desktop.interface.cli.commands.deep_dive import _enrich_topology_report_dict as enrich

    enrich(topo_dict)
    gate = compute_joint_overlay_datapath_gate(tp, cpe, topo_dict)

    html_text = out_path.read_text(encoding="utf-8", errors="replace")
    has_overlay_flow = 'class="topology-flow topology-flow-overlay"' in html_text

    path_checks, path_intent, path_outcome, path_bp = _path_matrix_checks(
        scenario, tp, cpe, topology
    )
    checks = {
        "rule_case": gate.rule_case == scenario.expected_rule_case,
        "evidence_tier": gate.evidence_tier == scenario.expected_evidence_tier,
        "show_overlay": gate.show_overlay_tunnel_strip == scenario.expected_show_overlay,
        "html_exists": out_path.is_file() and out_path.stat().st_size > 5000,
        "banner_present": (
            "report-joint-path-line" in html_text
            or "路径旁证（" in html_text
            or "路径结论:" in html_text
        ),
        "path_evidence_block": ("5200b" not in scenario.tags)
        or ("路径旁证（" in html_text),
        "path_analysis_html": ("path_matrix" not in scenario.tags)
        or ("声明业务路径（" in html_text),
        "path_evidence_l5_or_reach": ("path_matrix" not in scenario.tags)
        or ("路径旁证（" in html_text),
        "tier_label_ok": (
            (scenario.expected_evidence_tier != "heuristic")
            or ("启发式" in gate.datapath_banner)
        ),
        "precise_label_ok": (
            (scenario.expected_evidence_tier != "precise")
            or ("精确定位" in gate.datapath_banner)
        ),
        "url_group_in_banner": (
            "url-group" not in scenario.tags
            or "liveBroadcast" in gate.datapath_banner
            or "url-group" in gate.datapath_banner
        ),
        "overlay_strip_rendered": has_overlay_flow == scenario.expected_show_overlay,
    }
    checks.update(path_checks)

    return GeneratedScenarioReport(
        scenario_id=scenario.scenario_id,
        html_path=out_path,
        rule_case=gate.rule_case,
        evidence_tier=gate.evidence_tier,
        show_overlay=gate.show_overlay_tunnel_strip,
        suppress_overlay=not gate.show_overlay_tunnel_strip,
        banner_snippet=gate.datapath_banner[:120],
        path_config_intent=path_intent,
        path_reconcile_outcome=path_outcome,
        path_break_point=path_bp,
        checks=checks,
    )


def write_index_html(
    out_dir: Path,
    results: List[GeneratedScenarioReport],
    scenarios: List[JointReportScenario],
) -> Path:
    by_id = {s.scenario_id: s for s in scenarios}
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows: List[str] = []
    for r in results:
        sc = by_id[r.scenario_id]
        ok = all(r.checks.values())
        status = "PASS" if ok else "FAIL"
        fail_keys = [k for k, v in r.checks.items() if not v]
        path_col = ""
        if "path_matrix" in sc.tags:
            path_col = (
                f"<code>{r.path_config_intent}</code> / "
                f"{r.path_reconcile_outcome}"
                f"{(' / ' + r.path_break_point) if r.path_break_point else ''}"
            )
        rows.append(
            f"<tr class='{status.lower()}'>"
            f"<td><a href='{r.html_path.name}'>{r.scenario_id}</a></td>"
            f"<td>{sc.title}</td>"
            f"<td>{'联合诊断' if sc.joint_failure_driven else '核查通过'}</td>"
            f"<td><code>{r.rule_case}</code></td>"
            f"<td>{r.evidence_tier}</td>"
            f"<td>{'是' if r.show_overlay else '否'}</td>"
            f"<td>{path_col or '—'}</td>"
            f"<td>{status}</td>"
            f"<td>{', '.join(fail_keys) if fail_keys else '—'}</td>"
            f"<td style='font-size:0.85em'>{sc.description}</td>"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>业务联合报告仿真矩阵 · 目视验收索引</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f8fafc; }}
h1 {{ font-size: 1.35rem; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px #0001; }}
th, td {{ border: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; vertical-align: top; }}
th {{ background: #1e293b; color: #fff; }}
tr.pass td:nth-child(8) {{ color: #0d9488; font-weight: 700; }}
tr.fail td:nth-child(8) {{ color: #c62828; font-weight: 700; }}
code {{ font-size: 0.85em; }}
.meta {{ color: #64748b; margin-bottom: 16px; }}
</style></head><body>
<h1>业务联合报告 · 仿真矩阵目视验收</h1>
<p class="meta">生成时间 {ts} · 目录 <code>{out_dir}</code> · Phase E 门控 + 声明路径对账矩阵</p>
<p>验收要点：页首路径实证；5200B 场景含「url-group 与声明业务路径分析」；path_matrix 列校验 intent/reconcile/break_point。</p>
<table>
<thead><tr>
<th>场景 ID</th><th>标题</th><th>模式</th><th>rule_case</th><th>tier</th><th>Overlay</th><th>路径对账</th><th>自动校验</th><th>失败项</th><th>说明</th>
</tr></thead>
<tbody>
{''.join(rows)}
</tbody></table>
</body></html>"""
    index_path = out_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


def run_matrix(out_dir: Optional[Path] = None) -> tuple[Path, List[GeneratedScenarioReport]]:
    out = out_dir or _DEFAULT_OUT
    scenarios = all_scenarios()
    results = [generate_scenario_html(s, out) for s in scenarios]
    index = write_index_html(out, results, scenarios)
    return index, results
