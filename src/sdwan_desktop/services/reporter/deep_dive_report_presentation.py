"""纯深度诊断 HTML 页首结论与摘要区载荷（对齐业务路径诊断阅读顺序）。

与 ``joint_report_probe_outcome`` 分工：
- **业务联合**（``topology.report_html_h1``）仍写 ``report_joint_probe_outcome``，由 ``deep_dive_joint_ux.html`` 渲染；
- **纯深度诊断**写 ``report_deep_dive_outcome``，由 ``deep_dive.html`` 渲染。

测试点（采集命令、根因规则 ID）不变；本模块仅收敛**呈现层**主因/已排除/待核对分层。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity
from sdwan_desktop.services.reporter.joint_commercial_delivery import (
    _collect_tunnel_peer_ping_rows,
    failure_beyond_sdwan_edge_likely,
    joint_datapath_evidence_from_targeted_probe,
)
from sdwan_desktop.services.reporter.joint_report_probe_outcome import (
    _primary_fault_label,
    _secondary_findings,
    build_joint_report_probe_outcome,
)


def _biz_rows(targeted_probe: Optional[dict]) -> list[dict]:
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return []
    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return []
    rows = data.get("business_probes")
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _cpe_primary_narrative(
    *,
    causes: List[RootCause],
    cpe_unreachable: bool,
    issue_count: int,
    tunnel_rows: List[Dict[str, Any]],
    commercial_headline: Optional[str],
) -> str:
    if commercial_headline and commercial_headline.strip():
        return commercial_headline.strip()
    if cpe_unreachable:
        return (
            "未能连接 CPE 完成设备侧采集；以下为 PC 侧与可选业务探测结论。"
            "请优先恢复 SSH/管理面可达后再做专检。"
        )
    if issue_count == 0:
        if tunnel_rows and all(r.get("status") == "ok" for r in tunnel_rows):
            return (
                "CPE 可达；配置/隧道/策略专检未发现阻塞项，隧道对端 ICMP 探针正常。"
                "若仍有业务投诉，请叠加声明业务探测（--biz-target）或业务路径诊断。"
            )
        return (
            "CPE 可达；配置/隧道/策略专检未发现阻塞项。"
            "若仍有业务投诉，请叠加声明业务探测（--biz-target）或业务路径诊断。"
        )
    critical = sum(1 for c in causes if c.severity == Severity.CRITICAL)
    errors = sum(1 for c in causes if c.severity == Severity.ERROR)
    if critical or errors:
        return (
            f"CPE 可达；识别出 {issue_count} 项告警（含 {critical} 项严重、{errors} 项错误）。"
            "请结合下方根因卡片与证据链核对，并以原始命令输出为准。"
        )
    return (
        f"CPE 可达；识别出 {issue_count} 项待关注项（多为配置启发式）。"
        "请结合证据链逐项核对，避免将静态未命中直接等同于转发故障。"
    )


def _cpe_ruled_out(
    *,
    causes: List[RootCause],
    tunnel_rows: List[Dict[str, Any]],
) -> List[str]:
    out: List[str] = []
    if tunnel_rows and all(r.get("status") == "ok" for r in tunnel_rows):
        out.append("隧道对端 ICMP 探针均正常（未见整段 Underlay/隧道中断）")
    if not any(c.severity in (Severity.CRITICAL, Severity.ERROR) for c in causes):
        if not any(c.cause_id == "CPE-001" for c in causes):
            out.append("CPE 管理面可达（未触发 CPE-001）")
    if not causes:
        out.append("根因引擎未输出 CRITICAL/ERROR 级结论")
    return out[:5]


def _build_cpe_focused_outcome(
    *,
    diagnosis: DiagnosisResult,
    targeted_probe: Optional[dict],
    commercial_delivery: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    causes = list(diagnosis.root_causes or [])
    cpe_unreachable = any(c.cause_id == "CPE-001" for c in causes)
    raw = (
        (targeted_probe or {}).get("data", {}).get("raw_outputs")
        if isinstance(targeted_probe, dict)
        else {}
    )
    tunnel_rows: List[Dict[str, Any]] = []
    if isinstance(raw, dict):
        tunnel_rows = _collect_tunnel_peer_ping_rows(raw)

    if cpe_unreachable:
        phenomenon = "CPE 设备不可达，设备侧专检未完成"
    elif not causes:
        phenomenon = "CPE 可达；专检未发现需处置项"
    else:
        phenomenon = f"CPE 可达；专检识别 {len(causes)} 项告警"

    primary_fault = _primary_fault_label(
        causes,
        failure_stage="",
        beyond_tunnel_edge=False,
    )
    if not primary_fault and causes:
        top = sorted(
            causes,
            key=lambda c: (
                0 if c.severity == Severity.CRITICAL else
                1 if c.severity == Severity.ERROR else
                2 if c.severity == Severity.WARNING else 3
            ),
        )[0]
        primary_fault = (top.title or top.cause_id or "").strip()

    cd_headline = (
        commercial_delivery.get("headline")
        if isinstance(commercial_delivery, dict)
        else None
    )
    primary_narrative = _cpe_primary_narrative(
        causes=causes,
        cpe_unreachable=cpe_unreachable,
        issue_count=len(causes),
        tunnel_rows=tunnel_rows,
        commercial_headline=str(cd_headline) if cd_headline else None,
    )

    ruled_out = _cpe_ruled_out(causes=causes, tunnel_rows=tunnel_rows)
    secondary_findings = _secondary_findings(
        causes,
        primary_fault=primary_fault or "",
        beyond_tunnel_edge=False,
    )

    verdict = "需处理" if any(
        c.severity in (Severity.CRITICAL, Severity.ERROR) for c in causes
    ) else ("需关注" if causes else "正常")

    return {
        "mode": "cpe_focus",
        "verdict": verdict,
        "phenomenon": phenomenon,
        "primary_fault": primary_fault,
        "primary_narrative": primary_narrative,
        "ruled_out": ruled_out,
        "secondary_findings": secondary_findings,
        "has_business_probes": False,
    }


def build_deep_dive_report_outcome(
    *,
    diagnosis: DiagnosisResult,
    topology_dict: Dict[str, Any],
    targeted_probe: Optional[Dict[str, Any]],
    commercial_delivery: Optional[Dict[str, Any]] = None,
    cpe_configuration: Any = None,
) -> Dict[str, Any]:
    """生成写入 ``topology.report_deep_dive_outcome`` 的纯深度诊断页首/摘要载荷。"""
    rows = _biz_rows(targeted_probe)
    if rows:
        from sdwan_desktop.interface.cli.commands.business_diagnose import (
            _infer_business_failure_stage,
        )

        stage = _infer_business_failure_stage(targeted_probe)
        topology_dict.setdefault("business_failure_stage", stage)
        ev = joint_datapath_evidence_from_targeted_probe(targeted_probe)
        beyond = failure_beyond_sdwan_edge_likely(
            targeted_probe,
            ev,
            cpe_configuration=cpe_configuration,
            topology_dict=topology_dict,
        )
        topology_dict["business_fault_beyond_tunnel_edge"] = beyond

        biz_targets: List[str] = []
        for row in rows:
            dom = str(row.get("domain") or "")
            port = row.get("port")
            if dom:
                biz_targets.append(f"{dom}:{port}" if port else dom)

        joint = build_joint_report_probe_outcome(
            biz_targets=biz_targets,
            targeted_probe=targeted_probe,
            diagnosis=diagnosis,
            joint_failure_driven=False,
            business_failure_stage=stage,
            business_fault_beyond_tunnel_edge=beyond,
        )
        joint["mode"] = "with_business_probe"
        joint["verdict"] = (
            "需处理"
            if joint.get("overall") == "fail"
            else ("需关注" if joint.get("overall") == "partial" else "正常")
        )
        joint["has_business_probes"] = True
        return joint

    return _build_cpe_focused_outcome(
        diagnosis=diagnosis,
        targeted_probe=targeted_probe,
        commercial_delivery=commercial_delivery,
    )
