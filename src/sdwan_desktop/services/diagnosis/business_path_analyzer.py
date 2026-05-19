"""根据业务主机探测行（DNS + TCP + 可选路径追踪）生成根因列表（可与拓扑/CPE 结论合并）。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Sequence

from sdwan_desktop.core.types.diagnosis import RootCause, Severity
from sdwan_desktop.services.reporter.report_text_sanitize import sanitize_user_visible_text
from sdwan_desktop.tools.registry.decorator import pure_function

logger = logging.getLogger(__name__)


def _icmp_trace_path_hint_for_row(row: Dict[str, Any]) -> str:
    """从 ``row['trace']`` 提取一句旁证说明（ICMP 路径与 TCP 不等价，仅作阅读提示）。"""
    traces = row.get("trace") if isinstance(row.get("trace"), list) else []
    parts: List[str] = []
    for tr in traces:
        if not isinstance(tr, dict) or tr.get("status") != "ok":
            continue
        data = tr.get("data") if isinstance(tr.get("data"), dict) else {}
        summ = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        if summ.get("target_reached"):
            continue
        host = str(tr.get("host") or "")
        th = int(summ.get("total_hops") or 0)
        if host:
            parts.append(f"{host} ICMP 追踪 {th} 跳未标示到达目标")
    if not parts:
        return ""
    return " 路径旁证（ICMP traceroute，可能与 TCP 路径不一致）: " + "；".join(parts[:3]) + "。"


class BusinessPathAnalyzer:
    """从 ``business_probes`` 行数据归纳「业务不通」类根因（仅负面结论，避免刷屏）。"""

    @pure_function
    def analyze(self, business_probe_rows: Sequence[Dict[str, Any]]) -> List[RootCause]:
        """对探测结果逐目标生成根因。

        Args:
            business_probe_rows: ``run_business_domain_port_probes`` 返回的行列表（含可选 ``trace``）。

        Returns:
            ``RootCause`` 列表（可能为空，表示未发现明确异常形态）。
        """
        causes: List[RootCause] = []
        for row in business_probe_rows:
            domain = str(row.get("domain") or "")
            port = row.get("port")
            dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
            tcp_list = row.get("tcp") if isinstance(row.get("tcp"), list) else []

            dc = row.get("dns_comparison")
            if isinstance(dc, dict) and dc.get("split_v4"):
                causes.append(
                    RootCause(
                        cause_id="BIZ-DNS-SPLIT-001",
                        title=f"系统 DNS 与指定 DNS 解析结果不一致：{domain}",
                        description=(
                            f"`{domain}` 在系统解析与显式 DNS 服务器下得到的 IPv4 A 记录集合不同，"
                            "可能存在 DNS 分流、劫持或企业内/外双栈解析策略。请结合 PC 网卡 DNS 与 SD-WAN 策略核对。"
                        ),
                        severity=Severity.WARNING,
                        confidence=0.71,
                        evidence_refs=[domain, "dns_comparison"],
                        matched_rules=["BIZ-DNS-SPLIT"],
                    )
                )

            d_status = str(dns.get("status") or "")
            d_err = dns.get("error")

            if d_status == "error":
                causes.append(
                    RootCause(
                        cause_id="BIZ-DNS-001",
                        title=f"业务域名 DNS 解析失败：{domain}",
                        description=(
                            f"对 `{domain}` 的 A 记录查询失败。"
                            f"{(' 详情: ' + str(d_err)) if d_err else ''} "
                            "请检查本机 DNS、分流策略、上游 DNS 或域名拼写。"
                        ),
                        severity=Severity.ERROR,
                        confidence=0.74,
                        evidence_refs=[domain],
                        matched_rules=["BIZ-DNS-RESOLUTION"],
                    )
                )
                continue

            if d_status == "no_a":
                causes.append(
                    RootCause(
                        cause_id="BIZ-DNS-002",
                        title=f"业务域名无 IPv4 A 记录：{domain}",
                        description=(
                            f"`{domain}` 解析成功但无可用 IPv4 A 记录（可能仅为 AAAA 或空响应）。"
                            "若业务依赖 IPv4，请核查权威 DNS 或应用是否支持 IPv6。"
                        ),
                        severity=Severity.WARNING,
                        confidence=0.7,
                        evidence_refs=[domain],
                        matched_rules=["BIZ-DNS-NO-A"],
                    )
                )
                continue

            if d_status != "ok":
                continue

            if not tcp_list:
                continue

            any_open = False
            for t in tcp_list:
                if not isinstance(t, dict):
                    continue
                if t.get("status") != "ok":
                    continue
                data = t.get("data") if isinstance(t.get("data"), dict) else {}
                if data.get("port_open") is True:
                    any_open = True
                    break

            if not any_open:
                ips = ", ".join(
                    str(t.get("host"))
                    for t in tcp_list
                    if isinstance(t, dict) and t.get("host")
                )
                tcp_errs = [
                    sanitize_user_visible_text(str(t.get("error")))
                    for t in tcp_list
                    if isinstance(t, dict) and t.get("error")
                ]
                detail = ""
                if tcp_errs:
                    detail = " TCP 错误: " + "; ".join(tcp_errs[:3])
                timeout_like = any("timeout" in e.lower() or "超时" in e for e in tcp_errs)
                refused_like = any("refused" in e.lower() or "reset" in e.lower() for e in tcp_errs)
                if timeout_like:
                    cause_id = "BIZ-TCP-TIMEOUT-001"
                    title = f"业务 TCP 超时：{domain}:{port}"
                    reason_hint = "更符合“路径中间丢弃/黑洞或对端无响应”特征"
                elif refused_like:
                    cause_id = "BIZ-TCP-REFUSED-001"
                    title = f"业务 TCP 被拒绝：{domain}:{port}"
                    reason_hint = "更符合“对端端口未监听或被策略显式拒绝”特征"
                else:
                    cause_id = "BIZ-TCP-001"
                    title = f"业务 TCP 端口不可达：{domain}:{port}"
                    reason_hint = "请结合 CPE 策略、隧道状态与对端服务状态继续定位"
                icmp_hint = _icmp_trace_path_hint_for_row(row)
                causes.append(
                    RootCause(
                        cause_id=cause_id,
                        title=title,
                        description=(
                            f"从本机对解析地址 `{ips or '—'}` 的 TCP/{port} 探测未成功建立（超时或拒绝）。"
                            f"{detail} "
                            f"依据本次探针返回，该故障{reason_hint}。"
                            f"{icmp_hint}"
                        ),
                        severity=Severity.ERROR,
                        confidence=0.68,
                        evidence_refs=[domain, str(port)],
                        matched_rules=["BIZ-TCP-PORT-PROBE"],
                    )
                )

        logger.debug("BusinessPathAnalyzer: %d cause(s) from %d row(s)", len(causes), len(business_probe_rows))
        return causes
