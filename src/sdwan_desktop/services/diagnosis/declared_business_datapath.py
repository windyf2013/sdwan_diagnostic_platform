"""声明业务在 CPE 观测面上的转发路径可验证性（业务路径诊断 / 拓扑后信封）。

设计原则（准确性优先）
--------------------
网络诊断工具不得把「设备上存在大量隧道 / 隧道通断」与「**当前声明的** FQDN:端口
业务流是否经隧道或 Overlay 面转发」混为一谈。

**联合报告中的「Overlay 证据为正」** 由
``sdwan_desktop.services.diagnosis.raisecom_msg5200b_session.compute_joint_overlay_datapath_gate``
按产品规则计算（Raisecom 5200B 见 ``docs/rules/product_features/raisecom_msg5200b_network_analysis.md``
§5.2；非 5200B 设备为保守回退：仅当对声明目的地址的 nf_conntrack 采样存在非空行时为正）。

本模块的 ``targeted_probe_has_business_target_conntrack_hits`` 仍表示「对声明目的地址的
grep 是否出现非空会话行」，供证据链与 ``report_joint_nf_conntrack_had_session_lines`` 等字段使用；
**不得**单独用其布尔值替代上述 gate 驱动拓扑条带与根因过滤。

``infer_declared_business_datapath_verdict`` 若仍存在调用方，应与 gate 输出的
``declared_business_datapath_verdict``（``overlay_evidence_positive`` / ``unverified``）对齐；
遗留的一律 ``unverified`` 实现不应再作为联合 HTML/JSON 的唯一数据源。
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

DeclaredBusinessDatapathVerdict = Literal["overlay_evidence_positive", "unverified"]


def _biz_target_ips_from_targeted_data(data: Dict[str, Any]) -> List[str]:
    """从信封 ``data`` 提取业务目的 IPv4 列表（与 ``diagnose:nf_conntrack grep <ip>`` 键一致）。"""
    ips: List[str] = []
    for ip in data.get("biz_target_ips") or []:
        if ip and str(ip) not in ips:
            ips.append(str(ip))
    rows = data.get("business_probes")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
            dd = dns.get("data") if isinstance(dns.get("data"), dict) else {}
            for ip in dd.get("resolved_ips") or []:
                s = str(ip)
                if s and s not in ips:
                    ips.append(s)
            for t in row.get("tcp") or []:
                if isinstance(t, dict) and t.get("host"):
                    s = str(t.get("host"))
                    if s and s not in ips:
                        ips.append(s)
    return ips


def targeted_probe_has_business_target_conntrack_hits(
    targeted_probe: Optional[Dict[str, Any]],
) -> bool:
    """CPE 上对声明业务目的地址的 ``nf_conntrack grep`` 采样是否至少有一条非空行。

    用于联合报告：有命中则展示 Overlay 隧道示意条并允许启用 Overlay 证据链步骤；
    无命中则隐藏示意条并在拓扑区说明「当前采样下无法将声明流与隧道面建立观测关联」。
    """
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return False
    if targeted_probe.get("status") not in ("ok", "partial"):
        return False
    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return False
    rows = data.get("business_probes")
    if not isinstance(rows, list) or not rows:
        return False
    raw_outputs: Dict[str, Any] = dict(data.get("raw_outputs") or {})
    for ip in _biz_target_ips_from_targeted_data(data):
        key = f"diagnose:nf_conntrack grep {ip}"
        blob = str(raw_outputs.get(key) or "")
        for line in blob.splitlines():
            if line.strip():
                return True
    return False


def infer_declared_business_datapath_verdict(
    targeted_probe: Optional[Dict[str, Any]],
) -> DeclaredBusinessDatapathVerdict:
    """遗留占位：恒为 ``unverified``。联合报告请使用 ``compute_joint_overlay_datapath_gate``。"""
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return "unverified"
    if targeted_probe.get("status") not in ("ok", "partial"):
        return "unverified"
    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return "unverified"
    rows = data.get("business_probes")
    if not isinstance(rows, list) or not rows:
        return "unverified"
    return "unverified"


def declared_business_flow_has_verified_overlay_tunnel_evidence(
    targeted_probe: Optional[Dict[str, Any]],
) -> bool:
    """是否对声明目的地址存在 nf_conntrack 非空行（粗粒度；不含 5200B 策略前缀门控）。"""
    return targeted_probe_has_business_target_conntrack_hits(targeted_probe)
