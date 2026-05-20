"""拓扑后补充探测命令规划（按设备类型）。

Raisecom 补充说明（与 ``templates/whole_config_5200b.txt`` 一致）：

- **underlay**：业务出口通常为 ``ge1``，主采集模板已包含 ``show interface ge1``。
- **overlay**：vxlan/ipsec/l2tp 等接口名由主采集阶段根据配置/路由/link detect **动态追加**
  ``show interface <ifname>``（见 ``raisecom_interface_discovery``），不在此重复。
- **NAT 现表**：诊断视图 ``cat /proc/rcios/net/netfilter/nf_conntrack | grep "<ip>"``，
  仅对业务目的 IP 做 grep；**全量 nf_conntrack 数据量极大，禁止默认全采**。
- **ipset**：``ipset --list`` 用于已解析业务域名对应的 hash:ip 成员，诊断视图执行。
- **单目的 ``ip route get``**：设备侧暂不支持，不在此下发；替代方案由路由表 + ip rule + 策略表组合推断（预留）。
- **隧道对端探针**：仅对 ``vpn_tunnels`` 中的 **peer IP** 在诊断视图执行 ``ping -c 2``，**不对业务目的 IP 探针**。
  业务路径诊断联合流程通过 ``plan_post_topology_probe_commands(..., include_tunnel_peer_probes=False)``
  默认**不下发**该组命令，避免把「设备隧道库存可达性」误绑为「声明业务必经探测」；深度诊断保持默认下发。
- **PC↔CPE 间 NAT**：conntrack 中可能无真实 PC 源 IP；结论须与 PC 快照对照解读。
- **Overlay/策略分流证据链归纳**：深度诊断与业务联合流程在拓扑后探测之后执行
  ``sdwan_desktop.services.diagnosis.overlay_policy_flow_evidence``，用于报告中的核对清单与组网标签
  （**不断言** L2TP/IPsec/VXLAN 的线序封装）。
"""

from typing import Any, Dict, List, Set


def extract_tunnel_peer_ips_from_cpe_configuration(cpe_configuration: Any) -> List[str]:
    """从已解析的 ``CpeConfiguration.vpn_tunnels`` 收集隧道对端 IP（去重）。"""
    if cpe_configuration is None:
        return []
    peers: List[str] = []
    for t in getattr(cpe_configuration, "vpn_tunnels", None) or []:
        rip = (getattr(t, "remote_ip", None) or "").strip()
        if rip:
            peers.append(rip)
    return list(dict.fromkeys(peers))


def _dedupe_ips(biz_target_ips: List[str]) -> List[str]:
    return list(dict.fromkeys(ip for ip in biz_target_ips if ip))


def _build_nf_conntrack_probe_commands(
    biz_target_ips: List[str],
    *,
    save_as_prefix: str = "diagnose:nf_conntrack grep",
) -> List[Dict[str, Any]]:
    """为 Raisecom 生成基于业务目标 IP 的会话表查询命令。"""
    cmds: List[Dict[str, Any]] = []
    for ip in _dedupe_ips(biz_target_ips):
        cmds.append(
            {
                "name": f'diagnose:cat /proc/rcios/net/netfilter/nf_conntrack | grep "{ip}"',
                "priority": 0,
                "optional": True,
                "save_as": f"{save_as_prefix} {ip}",
            }
        )
    return cmds


def plan_baseline_conntrack_commands(biz_target_ips: List[str]) -> List[Dict[str, Any]]:
    """TCP 探测前 baseline nf_conntrack grep（业务路径联合诊断）。"""
    if not biz_target_ips:
        return []
    return _build_nf_conntrack_probe_commands(
        biz_target_ips,
        save_as_prefix="diagnose:nf_conntrack baseline grep",
    )


def plan_post_tcp_conntrack_commands(biz_target_ips: List[str]) -> List[Dict[str, Any]]:
    """TCP 完成后、traceroute 前的 post nf_conntrack grep。"""
    if not biz_target_ips:
        return []
    return _build_nf_conntrack_probe_commands(biz_target_ips)


def _raisecom_runtime_state_commands() -> List[Dict[str, Any]]:
    """Raisecom 运行态命令（路由/ipset/接口等；不含 conntrack）。"""
    return [
        {
            "name": "show link-protect status",
            "priority": 1,
            "optional": True,
            "save_as": "show link-protect status",
        },
        {
            "name": "show url-group all domain all",
            "priority": 1,
            "optional": True,
            "save_as": "show url-group all domain all",
        },
        {
            "name": "diagnose:ipset --list",
            "priority": 1,
            "optional": True,
            "save_as": "diagnose:ipset --list",
        },
        {
            "name": "show ip route",
            "priority": 1,
            "optional": True,
            "save_as": "show ip route",
        },
        {
            "name": "diagnose:ip rule show",
            "priority": 1,
            "optional": True,
            "save_as": "diagnose:ip rule show",
        },
        {
            "name": "diagnose:ip route show table 99",
            "priority": 1,
            "optional": True,
            "save_as": "diagnose:ip route show table 99",
        },
        {
            "name": "diagnose:ip route show table 100",
            "priority": 1,
            "optional": True,
            "save_as": "diagnose:ip route show table 100",
        },
        {
            "name": "diagnose:iptables -t mangle -nvL",
            "priority": 1,
            "optional": True,
            "save_as": "diagnose:iptables -t mangle -nvL",
        },
        {
            "name": "show interface ge1",
            "priority": 1,
            "optional": True,
            "save_as": "show interface ge1",
        },
        {
            "name": "show interface vlan1",
            "priority": 1,
            "optional": True,
            "save_as": "show interface vlan1",
        },
    ]


def plan_runtime_probe_commands(
    device_type: str,
    biz_target_ips: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """TCP 完成后立即下发的运行态命令（post conntrack 优先，再路由/ipset 等）。"""
    if device_type not in ("raisecom_msg5200", "raisecom_msg5200b", "raisecom_msg5200d"):
        return []
    cmds: List[Dict[str, Any]] = []
    if biz_target_ips:
        cmds.extend(plan_post_tcp_conntrack_commands(biz_target_ips))
    cmds.extend(_raisecom_runtime_state_commands())
    return cmds


def filter_commands_skip_keys(
    commands: List[Dict[str, Any]],
    skip_keys: Set[str],
) -> List[Dict[str, Any]]:
    """过滤 ``save_as`` 已在 ``skip_keys`` 中的命令。"""
    if not skip_keys:
        return list(commands)
    out: List[Dict[str, Any]] = []
    for cmd in commands:
        save_as = cmd.get("save_as", cmd.get("name", ""))
        if save_as in skip_keys:
            continue
        out.append(cmd)
    return out


def _build_tunnel_peer_ping_commands(peer_ips: List[str]) -> List[Dict[str, Any]]:
    """对隧道对端地址做轻量可达性探针（诊断 shell；不对业务目的 IP 探针）。"""
    cmds: List[Dict[str, Any]] = []
    for ip in peer_ips:
        cmds.append(
            {
                "name": f"diagnose:ping -c 2 {ip}",
                "priority": 2,
                "optional": True,
                "save_as": f"diagnose:ping tunnel_peer {ip}",
            }
        )
    return cmds


def plan_post_topology_probe_commands(
    device_type: str,
    biz_target_ips: List[str] | None = None,
    tunnel_peer_ips: List[str] | None = None,
    *,
    include_tunnel_peer_probes: bool = True,
    skip_keys: Set[str] | None = None,
) -> List[Dict[str, Any]]:
    """根据主采集阶段确定的 ``device_type`` 生成拓扑后探测命令列表。

    Raisecom 5200A/B：主采集已含 ``diagnose:ip rule`` 等；此处补充运行态与业务清单类命令。
    诊断 shell 入口由 ``CpeCollector`` 按 ``raisecom_msg5200b``/``raisecom_msg5200d``→``su``、``raisecom_msg5200``→``diagnose`` 路由。

    Args:
        device_type: ``ConfigParserRegistry`` / ``CpeCollector`` 设备标识。
        biz_target_ips: 业务探测目的 IP 列表；用于 nf_conntrack 的 grep（非全量）。
        tunnel_peer_ips: 隧道对端 IP 列表；用于诊断视图 ping，**不得**传入业务目的 IP。
        include_tunnel_peer_probes: 为 ``False`` 时不下发隧道 peer ICMP（业务路径诊断联合
            默认如此，避免把隧道库存探测误绑到声明业务）；深度诊断默认 ``True``。
        skip_keys: 已在并行 CPE 采集中执行的 ``save_as``，避免重复下发。

    Returns:
        与 ``CpeCollector._execute_commands`` 兼容的命令字典列表。
    """
    if device_type in ("raisecom_msg5200", "raisecom_msg5200b", "raisecom_msg5200d"):
        cmds = [
            {
                "name": "show link-protect status",
                "priority": 1,
                "optional": True,
                "save_as": "show link-protect status",
            },
            {
                "name": "show url-group all domain all",
                "priority": 1,
                "optional": True,
                "save_as": "show url-group all domain all",
            },
            {
                "name": "diagnose:ipset --list",
                "priority": 1,
                "optional": True,
                "save_as": "diagnose:ipset --list",
            },
        ]
        if biz_target_ips:
            cmds.extend(_build_nf_conntrack_probe_commands(_dedupe_ips(biz_target_ips)))
        if tunnel_peer_ips and include_tunnel_peer_probes:
            cmds.extend(_build_tunnel_peer_ping_commands(_dedupe_ips(tunnel_peer_ips)))
        return filter_commands_skip_keys(cmds, skip_keys or set())
    return []
