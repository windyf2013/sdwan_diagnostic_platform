"""为触发的诊断规则生成「当前值 / 合理值 / 证据」详情，供报告根因卡片展示。

每个 builder 返回一个 dict，约定字段：
- ``current_value``：当前观测值（一行文本，可在「根因」卡片直接展示）
- ``expected_value``：参考合理值（一行文本）
- ``evidence``：``List[str]``，逐条列出支撑结论的原始证据，供模板按列表渲染
  到「根因证据」区。每条证据应包含可被复核的具体数据（IP / 接口 / metric /
  RTT 等），而不是抽象描述。
"""

from typing import Any, Dict, List

from sdwan_desktop.services.analyzer.rules.system import find_ip_conflicts_from_arp


def build_rule_details(rule_id: str, ctx: Any) -> Dict[str, Any]:
    """返回 current_value、expected_value、evidence 三个键。

    Returns:
        Dict[str, Any]: 见模块文档；未注册的 rule_id 返回空 dict。
    """
    builders = {
        "GW-001": _gw_001,
        "GW-002": _gw_002,
        "GW-003": _gw_003,
        "DNS-001": _dns_001,
        "DNS-002": _dns_002,
        "INET-001": _inet_001,
        "INET-002": _inet_002,
        "INET-003": _inet_003,
        "INET-004": _inet_004,
        "ADAPTER-001": _adapter_001,
        "ADAPTER-002": _adapter_002,
        "IP-001": _ip_001,
        "IP-002": _ip_002,
        "ROUTE-001": _route_001,
        "ROUTE-002": _route_002,
        "PROXY-001": _proxy_001,
        "PROXY-002": _proxy_002,
        "FW-001": _fw_001,
        "IPV6-001": _ipv6_001,
    }
    fn = builders.get(rule_id)
    if fn is None:
        return {}
    return fn(ctx)


# ============================================================
# 辅助：把 RouteInfo 渲染为一条可读字符串
# ============================================================

def _format_route(route: Any) -> str:
    """将一条路由格式化为单行文本，例如：
    ``0.0.0.0/0 via 192.168.1.1 dev "Ethernet" metric 25 (dhcp)``
    """
    dest = getattr(route, "destination", "?") or "?"
    mask = getattr(route, "netmask", "") or ""
    gw = getattr(route, "gateway", "") or "on-link"
    iface = getattr(route, "interface", "") or "?"
    metric = getattr(route, "metric", None)
    protocol = getattr(route, "protocol", "") or ""

    dest_repr = f"{dest}/{mask}" if mask else dest
    metric_repr = "?" if metric is None else str(metric)
    proto_repr = f" ({protocol})" if protocol else ""

    return f"{dest_repr} via {gw} dev \"{iface}\" metric {metric_repr}{proto_repr}"


def _gw_001(ctx: Any) -> Dict[str, Any]:
    gw = (ctx.ip_config.default_gateway if ctx.ip_config else None) or "未知"
    gp = ctx.gateway_ping
    ok = gp and gp.success
    loss = 0.0
    rtt = None
    target = gw
    err = ""
    if gp:
        if gp.target is not None:
            target = getattr(gp.target, "host", None) or target
        if gp.metrics:
            if gp.metrics.loss_rate is not None:
                loss = gp.metrics.loss_rate * 100
            rtt = gp.metrics.rtt_avg
        err = getattr(gp, "error_message", "") or ""

    evidence: List[str] = [
        f"配置默认网关：{gw}",
        f"Ping 目标：{target}",
        f"探测结果：{'成功' if ok else '失败/超时'}",
        f"丢包率：{loss:.1f}%",
    ]
    if rtt is not None:
        evidence.append(f"平均 RTT：{rtt:.1f} ms")
    if err:
        evidence.append(f"错误信息：{err}")

    return {
        "current_value": f"网关 {gw} Ping {'成功' if ok else '失败/超时'}（丢包 {loss:.1f}%）",
        "expected_value": "网关应可 Ping 通（丢包率 < 5%）",
        "evidence": evidence,
    }


def _gw_002(ctx: Any) -> Dict[str, Any]:
    rtt = 0.0
    rtt_min = rtt_max = None
    gw = (ctx.ip_config.default_gateway if ctx.ip_config else None) or "未知"
    if ctx.gateway_ping and ctx.gateway_ping.metrics:
        rtt = ctx.gateway_ping.metrics.rtt_avg or 0.0
        rtt_min = ctx.gateway_ping.metrics.rtt_min
        rtt_max = ctx.gateway_ping.metrics.rtt_max

    evidence: List[str] = [
        f"网关地址：{gw}",
        f"平均 RTT：{rtt:.1f} ms",
    ]
    if rtt_min is not None:
        evidence.append(f"最小 RTT：{rtt_min:.1f} ms")
    if rtt_max is not None:
        evidence.append(f"最大 RTT：{rtt_max:.1f} ms")
    evidence.append("阈值：> 100 ms 视为偏高")

    return {
        "current_value": f"网关 RTT {rtt:.1f} ms",
        "expected_value": "局域网网关 RTT 通常 < 100 ms",
        "evidence": evidence,
    }


def _gw_003(ctx: Any) -> Dict[str, Any]:
    loss = 0.0
    sent = received = None
    gw = (ctx.ip_config.default_gateway if ctx.ip_config else None) or "未知"
    if ctx.gateway_ping and ctx.gateway_ping.metrics:
        m = ctx.gateway_ping.metrics
        loss = (m.loss_rate or 0.0) * 100
        sent = getattr(m, "packets_sent", None)
        received = getattr(m, "packets_received", None)

    evidence: List[str] = [
        f"网关地址：{gw}",
        f"丢包率：{loss:.1f}%",
    ]
    if sent is not None and received is not None:
        evidence.append(f"发送/收到：{sent}/{received} 个回显报文")
    evidence.append("阈值：> 5% 视为有丢包")

    return {
        "current_value": f"网关丢包率 {loss:.1f}%",
        "expected_value": "丢包率应 < 5%",
        "evidence": evidence,
    }


def _dns_001(ctx: Any) -> Dict[str, Any]:
    servers: List[str] = []
    if ctx.ip_config and ctx.ip_config.dns_servers:
        servers = list(ctx.ip_config.dns_servers)
    all_r = list(ctx.domestic_dns_results) + list(ctx.international_dns_results)
    ok = sum(1 for r in all_r if r.success)
    total = len(all_r)

    evidence: List[str] = [f"配置的 DNS 服务器：{', '.join(servers) if servers else '未配置'}"]
    for r in all_r:
        host = getattr(getattr(r, "target", None), "host", "?")
        rtt = None
        if getattr(r, "metrics", None):
            rtt = r.metrics.rtt_avg
        line = f"DNS {host}：{'响应正常' if r.success else '超时/失败'}"
        if rtt is not None:
            line += f"，RTT={rtt:.0f} ms"
        if not r.success and getattr(r, "error_message", ""):
            line += f"（{r.error_message}）"
        evidence.append(line)
    evidence.append(f"探测汇总：成功 {ok}/{total}")

    return {
        "current_value": f"DNS 服务器 {', '.join(servers) or '未配置'}；探测成功 {ok}/{total}",
        "expected_value": "至少一台 DNS 服务器响应正常",
        "evidence": evidence,
    }


def _dns_002(ctx: Any) -> Dict[str, Any]:
    rtts: List[float] = []
    evidence: List[str] = []
    for r in list(ctx.domestic_dns_results) + list(ctx.international_dns_results):
        host = getattr(getattr(r, "target", None), "host", "?")
        if r.success and r.metrics and r.metrics.rtt_avg is not None:
            rtts.append(r.metrics.rtt_avg)
            evidence.append(f"DNS {host}：RTT={r.metrics.rtt_avg:.0f} ms")
        else:
            evidence.append(f"DNS {host}：未取得 RTT 数据")
    avg = sum(rtts) / len(rtts) if rtts else 0.0
    evidence.append(f"平均 RTT：{avg:.0f} ms（阈值 500 ms）")

    return {
        "current_value": f"DNS 平均 RTT {avg:.0f} ms",
        "expected_value": "DNS 响应通常 < 500 ms",
        "evidence": evidence,
    }


def _inet_001(ctx: Any) -> Dict[str, Any]:
    total = len(ctx.domestic_target_results)
    ok = sum(1 for r in ctx.domestic_target_results if r.success)
    evidence: List[str] = [f"国内目标总数：{total}，可达 {ok}"]
    for r in ctx.domestic_target_results:
        host = getattr(getattr(r, "target", None), "host", "?")
        rtt = None
        if getattr(r, "metrics", None):
            rtt = r.metrics.rtt_avg
        line = f"{host}：{'可达' if r.success else '不可达'}"
        if rtt is not None:
            line += f"，RTT={rtt:.0f} ms"
        if not r.success and getattr(r, "error_message", ""):
            line += f"（{r.error_message}）"
        evidence.append(line)
    return {
        "current_value": f"国内探测目标可达 {ok}/{total}",
        "expected_value": "至少应有一个国内目标可达",
        "evidence": evidence,
    }


def _inet_002(ctx: Any) -> Dict[str, Any]:
    total = len(ctx.international_target_results)
    ok = sum(1 for r in ctx.international_target_results if r.success)
    evidence: List[str] = [f"国际目标总数：{total}，可达 {ok}"]
    for r in ctx.international_target_results:
        host = getattr(getattr(r, "target", None), "host", "?")
        rtt = None
        if getattr(r, "metrics", None):
            rtt = r.metrics.rtt_avg
        line = f"{host}：{'可达' if r.success else '不可达'}"
        if rtt is not None:
            line += f"，RTT={rtt:.0f} ms"
        if not r.success and getattr(r, "error_message", ""):
            line += f"（{r.error_message}）"
        evidence.append(line)
    return {
        "current_value": f"国际探测目标可达 {ok}/{total}",
        "expected_value": "至少应有一个国际目标可达",
        "evidence": evidence,
    }


def _inet_003(ctx: Any) -> Dict[str, Any]:
    loss_rates: List[float] = []
    evidence: List[str] = []
    for r in ctx.international_target_results:
        host = getattr(getattr(r, "target", None), "host", "?")
        if r.metrics and r.metrics.loss_rate is not None:
            loss_rates.append(r.metrics.loss_rate)
            evidence.append(f"{host}：丢包 {r.metrics.loss_rate * 100:.1f}%")
        else:
            evidence.append(f"{host}：无丢包指标")
    avg = (sum(loss_rates) / len(loss_rates) * 100) if loss_rates else 0.0
    evidence.append(f"平均丢包率：{avg:.1f}%（阈值 10%）")
    return {
        "current_value": f"国际链路平均丢包 {avg:.1f}%",
        "expected_value": "国际链路丢包率宜 < 10%",
        "evidence": evidence,
    }


def _inet_004(ctx: Any) -> Dict[str, Any]:
    failed: List[str] = []
    ok: List[str] = []
    evidence: List[str] = []
    for r in list(ctx.domestic_target_results) + list(ctx.international_target_results):
        host = getattr(getattr(r, "target", None), "host", "?")
        if r.success:
            ok.append(host)
        else:
            failed.append(host)
            err = getattr(r, "error_message", "") or "失败/超时"
            evidence.append(f"{host}：{err}")
    if not evidence:
        evidence.append("全部业务探针均成功")
    evidence.insert(0, f"失败 {len(failed)} 个；可达 {len(ok)} 个")
    failed_s = ", ".join(failed) if failed else "无"
    ok_s = ", ".join(ok) if ok else "无"
    return {
        "current_value": f"失败: {failed_s}；可达: {ok_s}",
        "expected_value": "全部业务探针（国内+国际）均应可达",
        "evidence": evidence,
    }


def _adapter_001(ctx: Any) -> Dict[str, Any]:
    name = "未知"
    mac = "未知"
    status = "未知"
    if ctx.primary_adapter:
        pa = ctx.primary_adapter
        name = pa.description or pa.name
        mac = pa.mac_address or "未知"
        status = "已连接" if pa.is_connected else "未连接"
    return {
        "current_value": f"主网卡 {name}：未连接",
        "expected_value": "主网卡应处于已连接状态",
        "evidence": [
            f"主网卡名称：{name}",
            f"MAC 地址：{mac}",
            f"连接状态：{status}",
        ],
    }


def _adapter_002(ctx: Any) -> Dict[str, Any]:
    name = "未知"
    speed = 0
    if ctx.primary_adapter:
        pa = ctx.primary_adapter
        name = pa.description or pa.name
        if pa.speed_mbps is not None:
            speed = pa.speed_mbps
    return {
        "current_value": f"协商速率 {speed} Mbps",
        "expected_value": "有线网卡宜 ≥ 100 Mbps",
        "evidence": [
            f"主网卡：{name}",
            f"协商速率：{speed} Mbps",
            "阈值：< 100 Mbps 视为偏低",
        ],
    }


def _ip_001(ctx: Any) -> Dict[str, Any]:
    ip = ctx.ip_config.ip_address if ctx.ip_config else "未知"
    dhcp = "未知"
    if ctx.ip_config is not None:
        dhcp = "DHCP" if ctx.ip_config.dhcp_enabled else "静态"
    return {
        "current_value": f"本机 IP {ip}",
        "expected_value": "应通过 DHCP 或静态配置获得有效私网/公网地址（非 169.254.x.x）",
        "evidence": [
            f"当前 IP：{ip}（APIPA 自动配置地址段）",
            f"地址来源：{dhcp}",
            "说明：169.254.x.x 表示 DHCP 失败、网卡自行回退到 APIPA",
        ],
    }


def _ip_002(ctx: Any) -> Dict[str, Any]:
    conflicts = find_ip_conflicts_from_arp(ctx.arp_table)
    if conflicts:
        parts = [f"{c['ip']}→{', '.join(c['macs'])}" for c in conflicts[:3]]
        cur = "；".join(parts)
        if len(conflicts) > 3:
            cur += f" 等{len(conflicts)}组"
    else:
        cur = "ARP 表存在重复 IP"
    evidence: List[str] = [f"ARP 表中冲突组数：{len(conflicts)}"]
    for c in conflicts[:10]:
        ifaces = "; ".join(f"{e['mac']}（{e['interface'] or '未知接口'}）" for e in c["entries"])
        evidence.append(f"IP {c['ip']}: {ifaces}")
    if len(conflicts) > 10:
        evidence.append(f"… 还有 {len(conflicts) - 10} 组冲突未列出")
    return {
        "current_value": cur,
        "expected_value": "同一 IP 仅应对应唯一 MAC",
        "evidence": evidence,
    }


def _route_001(ctx: Any) -> Dict[str, Any]:
    """ROUTE-001: 多条默认路由 —— 报告需明确列出每条默认路由。"""
    defaults = list(ctx.default_routes)
    n = len(defaults)

    # 当前值：精简一行，便于在「当前值/合理值」表中展示
    gw_metrics = []
    for r in defaults[:4]:
        gw_part = getattr(r, "gateway", "") or "on-link"
        m = getattr(r, "metric", None)
        gw_metrics.append(f"{gw_part}(metric={m if m is not None else '?'})")
    extra = f" 等{n}条" if n > 4 else ""
    current = f"默认路由 {n} 条：{'; '.join(gw_metrics)}{extra}"

    # 证据：逐条列出完整路由信息（目标网络/网关/接口/metric/协议）
    evidence: List[str] = [f"默认路由总数：{n}"]
    for idx, r in enumerate(defaults, 1):
        evidence.append(f"#{idx}  {_format_route(r)}")

    # 补充：与 ip_config 中记录的主默认网关做对比
    if ctx.ip_config and ctx.ip_config.default_gateway:
        evidence.append(f"系统 IP 配置中的默认网关：{ctx.ip_config.default_gateway}")

    return {
        "current_value": current,
        "expected_value": "通常仅 1 条活动默认路由；多链路场景宜由策略路由 / metric 区分主备",
        "evidence": evidence,
    }


def _route_002(ctx: Any) -> Dict[str, Any]:
    defaults = list(ctx.default_routes)
    if len(defaults) < 2:
        return {}
    metrics = [r.metric for r in defaults if r.metric is not None]
    if len(metrics) < 2:
        return {}

    evidence: List[str] = [
        f"默认路由总数：{len(defaults)}",
        f"metric 范围：{min(metrics)} – {max(metrics)}（差值 {max(metrics) - min(metrics)}，阈值 ≥ 50 视为差异显著）",
    ]
    for idx, r in enumerate(defaults, 1):
        evidence.append(f"#{idx}  {_format_route(r)}")

    return {
        "current_value": f"{len(defaults)} 条默认路由，metric 范围 {min(metrics)}–{max(metrics)}",
        "expected_value": "仅 1 条主用默认路由，或各默认路由 metric 接近（差值 < 50）",
        "evidence": evidence,
    }


def _proxy_001(ctx: Any) -> Dict[str, Any]:
    enabled = bool(ctx.proxy_config and ctx.proxy_config.enabled)
    server = ""
    bypass: List[str] = []
    if ctx.proxy_config:
        server = getattr(ctx.proxy_config, "server", "") or ""
        bypass = list(getattr(ctx.proxy_config, "bypass_list", []) or [])
    evidence: List[str] = [
        f"系统代理状态：{'已启用' if enabled else '未启用'}",
        f"代理服务器：{server or '未配置'}",
    ]
    if bypass:
        evidence.append(f"绕过列表：{', '.join(bypass[:5])}{' …' if len(bypass) > 5 else ''}")
    return {
        "current_value": f"系统代理 {'已启用' if enabled else '未启用'}{('：' + server) if server else ''}",
        "expected_value": "非必要场景建议关闭系统代理",
        "evidence": evidence,
    }


def _proxy_002(ctx: Any) -> Dict[str, Any]:
    addr = ""
    if ctx.proxy_config:
        addr = (
            getattr(ctx.proxy_config, "server", "")
            or getattr(ctx.proxy_config, "proxy_server", "")
            or ""
        )
    evidence: List[str] = [f"当前代理地址：{addr or '未配置'}"]
    if addr:
        has_protocol = "://" in addr
        server_after_proto = addr.split("//")[-1]
        has_port = ":" in server_after_proto
        evidence.append(f"包含协议（{'是' if has_protocol else '否'}）/包含端口（{'是' if has_port else '否'}）")
    evidence.append("期望格式示例：http://host:port 或 socks5://host:port")
    return {
        "current_value": f"代理地址 {addr or '无效'}",
        "expected_value": "代理地址应含协议与端口，如 http://host:port",
        "evidence": evidence,
    }


def _fw_001(ctx: Any) -> Dict[str, Any]:
    fw = ctx.firewall_status
    blocked = bool(fw and getattr(fw, "icmp_blocked", False))
    enabled = bool(fw and getattr(fw, "enabled", False))
    profiles = getattr(fw, "profiles", {}) if fw else {}
    evidence: List[str] = [
        f"防火墙总开关：{'开启' if enabled else '关闭/未知'}",
        f"ICMP 入站：{'被阻止' if blocked else '未知/未阻止'}",
    ]
    if profiles:
        evidence.append(
            "配置文件: " + ", ".join(f"{k}={'on' if v else 'off'}" for k, v in profiles.items())
        )
    return {
        "current_value": f"防火墙 ICMP 入站 {'被阻止' if blocked else '未知'}",
        "expected_value": "如需 Ping 本机，应放行回显请求规则",
        "evidence": evidence,
    }


def _ipv6_001(ctx: Any) -> Dict[str, Any]:
    ipv6 = ctx.ipv6
    enabled = bool(ipv6 and getattr(ipv6, "enabled", False))
    preferred = bool(ipv6 and getattr(ipv6, "is_preferred", False))
    addrs: List[str] = list(getattr(ipv6, "addresses", []) or []) if ipv6 else []
    evidence: List[str] = [
        f"IPv6 状态：{'已启用' if enabled else '未启用/未知'}",
        f"IPv6 优先：{'是' if preferred else '否'}",
    ]
    if addrs:
        evidence.append("IPv6 地址：" + ", ".join(addrs[:3]) + (" …" if len(addrs) > 3 else ""))
    return {
        "current_value": f"IPv6 {'已启用且优先' if preferred else ('已启用' if enabled else '未启用/未知')}",
        "expected_value": "按网络规划决定是否启用 IPv6",
        "evidence": evidence,
    }
