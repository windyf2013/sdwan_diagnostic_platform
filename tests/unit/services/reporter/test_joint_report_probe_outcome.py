"""joint_report_probe_outcome 页首结论块：单一主因 / 已排除 / 待核对分层。"""

from __future__ import annotations

from typing import Any, Dict, List

from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Severity
from sdwan_desktop.services.reporter.joint_report_probe_outcome import (
    _sanitize_probe_detail,
    build_joint_report_probe_outcome,
)


def _diagnosis(*causes: RootCause) -> DiagnosisResult:
    return DiagnosisResult(
        diagnosis_type="business_diagnosis_joint",
        summary="test",
        severity=Severity.ERROR,
        overall_confidence=0.8,
        root_causes=list(causes),
    )


def _cause(
    cause_id: str,
    title: str,
    severity: Severity = Severity.ERROR,
    description: str = "",
) -> RootCause:
    return RootCause(
        cause_id=cause_id,
        title=title,
        severity=severity,
        confidence=0.8,
        description=description,
        evidence_refs=[],
    )


def _tiktok_probe(*, dns_ok: bool = True, tcp_fail: bool = True) -> Dict[str, Any]:
    """构造类似 181552 的 TikTok 失败信封：DNS ok / TCP 超时 / conntrack 命中 + SYN-only。"""
    biz_ip = "31.13.92.37"
    tcp = []
    if tcp_fail:
        tcp = [
            {
                "host": biz_ip,
                "port": 443,
                "status": "fail",
                "error": "[TOOL_TIMEOUT] 工具 tcping 执行超时 (10s) (trace_id: x-1)",
            }
        ]
    return {
        "status": "ok",
        "data": {
            "business_probes": [
                {
                    "domain": "www.tiktok.com",
                    "port": 443,
                    "dns": {
                        "status": "ok" if dns_ok else "fail",
                        "data": {"resolved_ips": [biz_ip]},
                    },
                    "tcp": tcp,
                    "trace": [],
                }
            ],
            "biz_target_ips": [biz_ip],
            "raw_outputs": {
                "diagnose:ping tunnel_peer 198.51.100.2": (
                    "2 packets transmitted, 2 received, 0% packet loss"
                ),
                f"diagnose:nf_conntrack grep {biz_ip}": (
                    f"ipv4 2 tcp 6 60 SYN_SENT src=10.10.100.161 dst={biz_ip} "
                    f"sport=53000 dport=443 [UNREPLIED] src={biz_ip} dst=10.10.100.161 "
                    "sport=443 dport=53000"
                ),
            },
        },
    }


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def test_sanitize_probe_detail_strips_trace_id_and_tool_prefix() -> None:
    raw = "[TOOL_TIMEOUT] 工具 tcping 执行超时 (10s) (trace_id: abc-def)"
    out = _sanitize_probe_detail(raw)
    assert "trace_id" not in out
    assert "TOOL_TIMEOUT" not in out
    assert "超时" in out


# ---------------------------------------------------------------------------
# 181552 场景：beyond_tunnel=True + CPE-003/004 启发式 → 主因唯一，不并列 NAT
# ---------------------------------------------------------------------------


def test_tiktok_beyond_tunnel_primary_fault_is_singular_remote() -> None:
    """beyond_tunnel=True 时主因为「公网/对端路径不可达」单一项；
    CPE-003/004 不进入 primary_fault，仅作为 secondary_findings。"""
    out = build_joint_report_probe_outcome(
        biz_targets=["www.tiktok.com:443"],
        targeted_probe=_tiktok_probe(),
        diagnosis=_diagnosis(
            _cause("BIZ-TCP-TIMEOUT-001", "业务 TCP 超时：www.tiktok.com:443", Severity.ERROR),
            _cause("CPE-003", "PC 与 SD-WAN 策略源前缀未匹配", Severity.WARNING),
            _cause("CPE-004", "PC 网段未覆盖 CPE NAT inside", Severity.WARNING),
        ),
        joint_failure_driven=True,
        business_failure_stage={"stage": "tcp_connect"},
        business_fault_beyond_tunnel_edge=True,
    )

    # 主因：单一标签，无「；」拼接，与「公网/对端路径」一致。
    assert out["primary_fault"] == "公网/对端路径不可达"
    assert "；" not in out["primary_fault"]
    assert "CPE 配置" not in out["primary_fault"]
    assert "NAT" not in out["primary_fault"]

    # 兼容字段：fault_summary = primary_fault；fault_causes 仅含主因（不再为多元素列表）
    assert out["fault_summary"] == out["primary_fault"]
    assert out["fault_causes"] == ["公网/对端路径不可达"]

    # 主叙述与商用交付摘要同源（包含「隧道对端网络层可达」与「SYN」等关键词）。
    assert "隧道对端网络层可达" in out["primary_narrative"]
    assert "SYN" in out["primary_narrative"]

    # 已排除：DNS 正常 + 隧道 ICMP 正常 + conntrack 命中 + 已离开 CPE 邻域。
    ruled_out_text = " | ".join(out["ruled_out"])
    assert "DNS" in ruled_out_text
    assert "隧道对端" in ruled_out_text
    assert "conntrack" in ruled_out_text
    assert "CPE 邻域" in ruled_out_text

    # 待核对：CPE-003/004 必须出现且文案明确「待核对」「不得等同于」。
    ids = {f["id"] for f in out["secondary_findings"]}
    assert {"CPE-003", "CPE-004"}.issubset(ids)
    for f in out["secondary_findings"]:
        if f["id"] in {"CPE-003", "CPE-004"}:
            assert "待核对" in f["label"]
            assert "静态" in f["note"]

    # 探测明细仍在 results 中可见，未删减。
    assert out["results"][0]["target"] == "www.tiktok.com:443"
    assert out["results"][0]["dns_status"] == "ok"
    assert out["results"][0]["tcp_status"] == "fail"
    assert "trace_id" not in out["results"][0]["tcp_detail"]


# ---------------------------------------------------------------------------
# CPE-001：硬故障 → 主因为 CPE 不可达，无对端主因混入
# ---------------------------------------------------------------------------


def test_primary_fault_cpe_unreachable_overrides_remote() -> None:
    out = build_joint_report_probe_outcome(
        biz_targets=[],
        targeted_probe=None,
        diagnosis=_diagnosis(
            _cause("CPE-001", "CPE 管理面不可达", Severity.CRITICAL),
        ),
        joint_failure_driven=True,
    )
    assert out["primary_fault"] == "CPE 不可达"
    assert out["fault_summary"] == "CPE 不可达"
    # 无业务探测信封时，ruled_out 应为空（不写空话）
    assert out["ruled_out"] == []


# ---------------------------------------------------------------------------
# DNS 失败：stage=dns → 主因为 DNS
# ---------------------------------------------------------------------------


def test_primary_fault_dns_when_failure_stage_dns() -> None:
    probe = _tiktok_probe(dns_ok=False, tcp_fail=False)
    out = build_joint_report_probe_outcome(
        biz_targets=["www.tiktok.com:443"],
        targeted_probe=probe,
        diagnosis=_diagnosis(
            _cause("BIZ-TCP-DNS-001", "DNS 解析失败", Severity.ERROR),
        ),
        joint_failure_driven=True,
        business_failure_stage={"stage": "dns"},
        business_fault_beyond_tunnel_edge=False,
    )
    assert out["primary_fault"] == "DNS 解析失败"


# ---------------------------------------------------------------------------
# 域内 TCP 失败：beyond_tunnel=False → 主因为「服务器不可达」
# ---------------------------------------------------------------------------


def test_primary_fault_in_domain_tcp_failure() -> None:
    probe = _tiktok_probe()
    out = build_joint_report_probe_outcome(
        biz_targets=["www.tiktok.com:443"],
        targeted_probe=probe,
        diagnosis=_diagnosis(
            _cause("BIZ-TCP-TIMEOUT-001", "TCP 超时", Severity.ERROR),
            _cause("CPE-003", "策略未命中", Severity.WARNING),
        ),
        joint_failure_driven=True,
        business_failure_stage={"stage": "tcp_connect"},
        business_fault_beyond_tunnel_edge=False,
    )
    assert out["primary_fault"] == "服务器不可达"
    # 即便 beyond=False，CPE-003 仍以「待核对」呈现（非主因）
    ids = {f["id"] for f in out["secondary_findings"]}
    assert "CPE-003" in ids
    assert "公网/对端" not in out["primary_fault"]


# ---------------------------------------------------------------------------
# 业务探测全 OK：不应给出故障主因
# ---------------------------------------------------------------------------


def test_tcp_ok_but_port_closed_is_fail_phenomenon_not_probe_pass() -> None:
    """status=tcp ok 且 port_open=false 须与 _infer_business_failure_stage(server_port) 一致，禁止写「探测通过」。"""
    targeted_probe: Dict[str, Any] = {
        "status": "ok",
        "data": {
            "business_probes": [
                {
                    "domain": "www.tiktok.com",
                    "port": 443,
                    "dns": {"status": "ok", "data": {"resolved_ips": ["185.45.5.35"]}},
                    "tcp": [
                        {
                            "host": "185.45.5.35",
                            "port": 443,
                            "status": "ok",
                            "data": {"port_open": False, "response_time_avg": 10.0},
                        }
                    ],
                    "trace": [],
                }
            ],
        },
    }
    out = build_joint_report_probe_outcome(
        biz_targets=["www.tiktok.com:443"],
        targeted_probe=targeted_probe,
        diagnosis=_diagnosis(_cause("BIZ-TCP-PORT-001", "端口不可达", Severity.ERROR)),
        joint_failure_driven=True,
        business_failure_stage={"stage": "server_port"},
        business_fault_beyond_tunnel_edge=True,
    )
    assert out["overall"] == "fail"
    assert "探测通过" not in out["phenomenon"]
    assert "端口" in out["phenomenon"] or "拒绝" in out["phenomenon"]
    assert out["results"][0]["tcp_status"] == "fail"


def test_no_primary_fault_when_all_business_probes_ok() -> None:
    targeted_probe: Dict[str, Any] = {
        "status": "ok",
        "data": {
            "business_probes": [
                {
                    "domain": "ok.example",
                    "port": 80,
                    "dns": {"status": "ok", "data": {"resolved_ips": ["10.0.0.1"]}},
                    "tcp": [
                        {
                            "host": "10.0.0.1",
                            "port": 80,
                            "status": "ok",
                            "data": {"port_open": True},
                        }
                    ],
                    "trace": [
                        {
                            "host": "10.0.0.1",
                            "status": "ok",
                            "data": {"summary": {"target_reached": True, "total_hops": 3}},
                        }
                    ],
                }
            ]
        },
    }
    out = build_joint_report_probe_outcome(
        biz_targets=[],
        targeted_probe=targeted_probe,
        diagnosis=_diagnosis(),
        joint_failure_driven=False,
    )
    assert out["overall"] == "ok"
    assert out["primary_fault"] == ""
    assert out["fault_summary"] == ""
    assert "DNS/TCP 探测通过" in out["phenomenon"]
    # 业务已通时主叙述应为「可达性基线」类
    assert "本机业务探测" in out["primary_narrative"]


# ---------------------------------------------------------------------------
# 隧道 peer ICMP 失败：主叙述与商用交付摘要 headline 同源（隧道存疑）
# ---------------------------------------------------------------------------


def test_primary_narrative_aligned_with_delivery_when_tunnel_ping_fail() -> None:
    from sdwan_desktop.services.reporter.joint_commercial_delivery import (
        build_commercial_delivery_payload,
    )

    biz_ip = "203.0.113.10"
    targeted_probe: Dict[str, Any] = {
        "status": "partial",
        "data": {
            "business_probes": [
                {
                    "domain": "svc.example",
                    "port": 443,
                    "dns": {"status": "ok", "data": {"resolved_ips": [biz_ip]}},
                    "tcp": [
                        {"host": biz_ip, "port": 443, "status": "fail", "error": "timeout"}
                    ],
                }
            ],
            "biz_target_ips": [biz_ip],
            "raw_outputs": {
                "diagnose:ping tunnel_peer 198.51.100.2": (
                    "2 packets transmitted, 0 received, 100% packet loss"
                ),
            },
        },
    }
    diag = _diagnosis(
        _cause("BIZ-TCP-TIMEOUT-001", "业务 TCP 超时", Severity.ERROR),
    )
    delivery = build_commercial_delivery_payload(
        trace_id="t-align",
        diagnosis=diag,
        topology_dict={"pc_snapshot_included": True},
        targeted_probe=targeted_probe,
    )
    assert delivery is not None
    hero = build_joint_report_probe_outcome(
        biz_targets=["svc.example:443"],
        targeted_probe=targeted_probe,
        diagnosis=diag,
        joint_failure_driven=True,
        business_failure_stage={"stage": "tcp_connect"},
        business_fault_beyond_tunnel_edge=False,
    )
    # 字符串级一致：避免「页首一种说法、交付摘要另一种说法」
    assert hero["primary_narrative"] == delivery.headline
