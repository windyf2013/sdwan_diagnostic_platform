"""三条产品线（QuickCheck / BusinessDiagnose / DeepDive）共用的商用报告元数据。

用于 HTML 扉页与 CLI JSON 顶层 ``report_pack``，与 ``joint_commercial_delivery`` 业务阅读层职责分离。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.diagnosis import DiagnosisResult


def biz_targets_from_business_probes(rows: Optional[List[Dict[str, Any]]]) -> List[str]:
    """从探测行构造 ``domain:port`` 展示列表（用于扉页）。"""
    out: List[str] = []
    if not isinstance(rows, list):
        return out
    for r in rows:
        if not isinstance(r, dict):
            continue
        d = str(r.get("domain") or "").strip()
        if not d:
            continue
        port = r.get("port")
        if port is not None and str(port).strip():
            out.append(f"{d}:{port}")
        else:
            out.append(d)
    return out[:24]


def biz_targets_from_targeted_probe(targeted_probe: Optional[Dict[str, Any]]) -> List[str]:
    """从联合诊断信封提取声明目标列表。"""
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return []
    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return []
    return biz_targets_from_business_probes(data.get("business_probes"))  # type: ignore[arg-type]


class ReportProductLine(str, Enum):
    """报告所属产品线（与 spec 章节「〇」对齐）。"""

    QUICK_CHECK = "quick_check"
    BUSINESS_DIAGNOSE = "business_diagnose"
    DEEP_DIVE = "deep_dive"


@dataclass(frozen=True, slots=True)
class EvidenceTierLine:
    """单条证据层级说明（供模板列表渲染）。"""

    tier: str
    title: str
    detail: str

    def as_dict(self) -> Dict[str, str]:
        return {"tier": self.tier, "title": self.title, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class ReportDeliveryPack:
    """商用交付用报告包元数据（序列化后注入 Jinja / JSON）。"""

    product_line: ReportProductLine
    product_title: str
    product_subtitle: str
    trace_id: str
    report_id: str
    generated_at_iso: str
    rule_version: str
    joint_mode: bool
    evidence_tiers: tuple[EvidenceTierLine, ...] = field(default_factory=tuple)
    scope_included: tuple[str, ...] = field(default_factory=tuple)
    scope_excluded: tuple[str, ...] = field(default_factory=tuple)
    handoff_hints: tuple[str, ...] = field(default_factory=tuple)
    audit_note: str = ""

    def as_template_dict(self) -> Dict[str, Any]:
        return {
            "product_line": self.product_line.value,
            "product_title": self.product_title,
            "product_subtitle": self.product_subtitle,
            "trace_id": self.trace_id,
            "report_id": self.report_id,
            "generated_at_iso": self.generated_at_iso,
            "rule_version": self.rule_version,
            "joint_mode": self.joint_mode,
            "evidence_tiers": [x.as_dict() for x in self.evidence_tiers],
            "scope_included": list(self.scope_included),
            "scope_excluded": list(self.scope_excluded),
            "handoff_hints": list(self.handoff_hints),
            "audit_note": self.audit_note,
        }


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_quick_check_pack(*, result: DiagnosisResult, generated_at_iso: Optional[str] = None) -> ReportDeliveryPack:
    """一键体检：L1 本机为主，不包含 CPE 专检。"""
    ts = generated_at_iso or _utc_iso_now()
    tiers = (
        EvidenceTierLine("L1", "本机证据", "系统快照、网关、DNS、典型连通性与分流探测结果。"),
        EvidenceTierLine("L2", "设备侧证据", "本报告默认不包含；需 CPE 时请使用深度诊断或业务路径诊断（联合）。"),
        EvidenceTierLine("L3", "对端/运营商协同", "本报告不包含；跨域策略需对端配合取证。"),
    )
    included = (
        "本机系统与网络环境采集",
        "规则引擎汇总的根因与建议",
    )
    excluded = (
        "CPE 配置解析、隧道 BFD、全量策略表审计",
        "针对单一业务 FQDN:端口的端到端 SLA（请用业务路径诊断）",
    )
    hints = (
        "若问题与特定业务域名/端口相关：使用 agentctl business-diagnose（或 GUI「业务路径诊断」）并带上 -b FQDN:端口。",
        "若需对 CPE 做专检：使用 agentctl deep-dive（或 GUI「深度诊断」）并提供 CPE 凭证。",
    )
    audit = (
        "本流程默认不落 CPE 登录口令；若您在命令行传入密码，请避免将控制台输出与报告一并提交至不可信第三方。"
    )
    return ReportDeliveryPack(
        product_line=ReportProductLine.QUICK_CHECK,
        product_title="一键体检（Quick Check）",
        product_subtitle="客户端环境与基础连通性自助核查",
        trace_id=result.trace_id,
        report_id=result.id,
        generated_at_iso=ts,
        rule_version=result.rule_version or "1.0.0",
        joint_mode=False,
        evidence_tiers=tiers,
        scope_included=included,
        scope_excluded=excluded,
        handoff_hints=hints,
        audit_note=audit,
    )


def build_business_diagnose_pack(
    *,
    result: DiagnosisResult,
    joint_mode: bool,
    biz_targets: Optional[List[str]] = None,
    generated_at_iso: Optional[str] = None,
    joint_failure_driven: Optional[bool] = None,
) -> ReportDeliveryPack:
    """业务路径诊断：以声明探测目标为锚；联合模式含 L2 CPE 采样。"""
    ts = generated_at_iso or _utc_iso_now()
    targets = biz_targets or []
    target_note = "、".join(targets) if targets else "（见报告内探测表）"
    if joint_mode:
        if joint_failure_driven is True:
            product_title = "业务路径联合深挖（Business Joint · Post-failure）"
        elif joint_failure_driven is False:
            product_title = "业务路径联合核查（Business Joint · Verify）"
        else:
            product_title = "业务路径联合分析（Business Joint）"
        subtitle = f"PC + CPE 联合核查（声明目标：{target_note}）"
        tiers = (
            EvidenceTierLine("L1", "本机证据", "DNS 与 TCP 探测、可选 PC 快照。"),
            EvidenceTierLine(
                "L2",
                "CPE 采样",
                "拓扑后探测（nf_conntrack grep 业务目的 IP、ipset 等；业务路径模式默认不含隧道 peer 全量 ICMP，以设备与规划为准）。",
            ),
            EvidenceTierLine("L3", "对端/运营商协同", "回程、目的侧 ACL、清洗等需对端或线路侧配合。"),
        )
        included = (
            "声明业务目标的 DNS/TCP 探测结果",
            "CPE 采集与业务视角拓扑（若已连接 CPE）",
            "商用交付摘要（阅读层归纳，不替代根因规则结论）",
        )
    else:
        subtitle = f"本机业务探测（声明目标：{target_note}）"
        tiers = (
            EvidenceTierLine("L1", "本机证据", "DNS 与 TCP 探测、可选 PC 快照。"),
            EvidenceTierLine("L2", "设备侧证据", "本报告未连接 CPE 时未采集；失败场景请提供 CPE 参数以生成联合报告。"),
            EvidenceTierLine("L3", "对端/运营商协同", "与 L1/L2 证据矛盾时以原始输出为准并安排复测。"),
        )
        included = (
            "声明业务目标的 DNS/TCP 探测结果",
            "可选 PC 快照摘要",
        )
    excluded = (
        "与声明目标无关的全量 CPE 配置审计（请用深度诊断）",
        "全业务矩阵扫描（一次运行锚定一条或一组声明目标）",
    )
    hints = (
        "若需 CPE/隧道/策略专检：使用 agentctl deep-dive。",
        "若仅需本机环境初判：使用 agentctl quick-check。",
    )
    audit = (
        "联合模式将连接 CPE；请使用受控凭证文件并限制报告分发范围。"
    )
    if not joint_mode:
        product_title = "业务路径诊断（Business Diagnose）"
    return ReportDeliveryPack(
        product_line=ReportProductLine.BUSINESS_DIAGNOSE,
        product_title=product_title,
        product_subtitle=subtitle,
        trace_id=result.trace_id,
        report_id=result.id,
        generated_at_iso=ts,
        rule_version=result.rule_version or "1.0.0",
        joint_mode=joint_mode,
        evidence_tiers=tiers,
        scope_included=included,
        scope_excluded=excluded,
        handoff_hints=hints,
        audit_note=audit,
    )


def build_deep_dive_pack(
    *,
    result: DiagnosisResult,
    has_business_probe: bool = False,
    generated_at_iso: Optional[str] = None,
) -> ReportDeliveryPack:
    """深度诊断：运维侧 CPE 专检，可选叠加本机与业务探测。"""
    ts = generated_at_iso or _utc_iso_now()
    if has_business_probe:
        subtitle = "CPE 配置与运行态专检（已叠加可选业务探测）"
        tiers = (
            EvidenceTierLine("L1", "本机输入", "PC 快照与本地探测作为上下文。"),
            EvidenceTierLine("L2", "CPE 证据", "采集、解析与拓扑后探测（依设备类型与规划）。"),
            EvidenceTierLine("L3", "对端/运营商协同", "跨域路径需对端抓包或线路侧配合。"),
        )
    else:
        subtitle = "CPE 配置与运行态专检（未声明业务探测目标时以设备健康为主）"
        tiers = (
            EvidenceTierLine("L1", "本机输入", "可选 PC 快照，用于与 CPE 策略/NAT 对齐。"),
            EvidenceTierLine("L2", "CPE 证据", "配置解析、Overlay/Underlay 与规则引擎结论。"),
            EvidenceTierLine("L3", "对端/运营商协同", "见根因描述中的外部协同提示。"),
        )
    included = (
        "CPE 连接、采集与根因分析",
        "网络拓扑与（若启用）拓扑后探测输出",
    )
    if has_business_probe:
        included = included + ("命令行声明的业务探测行（若存在）",)
    excluded = (
        "不等价于「仅本机」一键体检（请用 quick-check）",
        "非「单业务 SLA 交付包」的默认叙事（单业务留档请用 business-diagnose）",
    )
    hints = (
        "若用户侧仅关心单一业务 FQDN:端口：使用 agentctl business-diagnose。",
        "若仅需本机网络/DNS 初判：使用 agentctl quick-check。",
    )
    audit = (
        "深度诊断可含 CPE 配置片段与探测原始输出；请按组织数据分级策略存储与外传。"
    )
    return ReportDeliveryPack(
        product_line=ReportProductLine.DEEP_DIVE,
        product_title="深度诊断（Deep Dive）",
        product_subtitle=subtitle,
        trace_id=result.trace_id,
        report_id=result.id,
        generated_at_iso=ts,
        rule_version=result.rule_version or "1.0.0",
        joint_mode=False,
        evidence_tiers=tiers,
        scope_included=included,
        scope_excluded=excluded,
        handoff_hints=hints,
        audit_note=audit,
    )
