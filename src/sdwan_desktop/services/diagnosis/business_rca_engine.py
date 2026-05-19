"""业务不通：多源证据融合与假设生成（与 ``BusinessPathAnalyzer`` 分层）。"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from sdwan_desktop.core.types.business_rca import (
    BusinessRCAFinding,
    Hypothesis,
    ObservationContext,
    PCObservationSummary,
    ProbeBundle,
)
from sdwan_desktop.core.types.diagnosis import RootCause, Severity
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.diagnosis.business_path_analyzer import BusinessPathAnalyzer
from sdwan_desktop.services.topology.topology import NetworkTopology
from sdwan_desktop.tools.registry.decorator import pure_function

logger = logging.getLogger(__name__)


class HypothesisGenerator:
    """基于观测与探针生成可人工复核的假设列表（不直接等价于根因）。"""

    @staticmethod
    @pure_function
    def generate(obs: ObservationContext, bundle: ProbeBundle) -> List[Hypothesis]:
        """生成若干条与 SD-WAN 业务路径相关的假设。"""
        hyps: List[Hypothesis] = []
        refs = [obs.trace_id, "probe_bundle"]
        if not bundle.business_probes:
            hyps.append(
                Hypothesis(
                    hypothesis_id="H-NO-PROBE",
                    statement="未执行业务目标探测或探测数据为空。",
                    evidence_refs=refs,
                )
            )
            return hyps
        doms = [str(r.get("domain") or "") for r in bundle.business_probes if r.get("domain")]
        if doms:
            hyps.append(
                Hypothesis(
                    hypothesis_id="H-DNS-PATH",
                    statement="命名解析或 DNS 分流导致解析结果与业务预期不一致。",
                    evidence_refs=refs + doms[:3],
                )
            )
            hyps.append(
                Hypothesis(
                    hypothesis_id="H-TCP-EGRESS",
                    statement="本机出站路径（默认路由/多网卡/代理）导致 TCP 与业务实际路径不一致。",
                    evidence_refs=refs + ["pc_egress"],
                )
            )
        # 与 ``business_host_probe`` 的 ``trace`` 列对齐：ICMP/UDP 追踪为旁证，不等价于业务 TCP 面。
        has_trace_ok = False
        for r in bundle.business_probes:
            trs = r.get("trace") if isinstance(r.get("trace"), list) else []
            if any(isinstance(t, dict) and t.get("status") == "ok" for t in trs):
                has_trace_ok = True
                break
        if has_trace_ok:
            hyps.append(
                Hypothesis(
                    hypothesis_id="H-ICMP-TRACE",
                    statement=(
                        "本机路由追踪（traceroute）已采样；若中间设备丢弃探测报文或与 TCP 选路不一致，"
                        "应仅作路径旁证并结合 CPE/会话证据解读。"
                    ),
                    evidence_refs=refs + ["traceroute"],
                )
            )
        if obs.cpe_evidence_available:
            hyps.append(
                Hypothesis(
                    hypothesis_id="H-SDWAN-POLICY",
                    statement="CPE 侧策略路由或选路将此类目的流量送至非预期 WAN 或 Overlay。",
                    evidence_refs=refs + ([obs.cpe_node_id] if obs.cpe_node_id else []),
                )
            )
        else:
            hyps.append(
                Hypothesis(
                    hypothesis_id="H-CPE-UNKNOWN",
                    statement="缺少 CPE 配置与隧道状态时，无法验证 SD-WAN 策略面；结论仅限本机段。",
                    evidence_refs=refs,
                )
            )
        return hyps


class BusinessRCAEngine:
    """融合 PC 观测边界与 ``ProbeBundle``，输出带上下文的 ``RootCause``。"""

    def __init__(self) -> None:
        self._path_analyzer = BusinessPathAnalyzer()
        self._hypothesis_gen = HypothesisGenerator()

    def hypotheses(self, obs: ObservationContext, bundle: ProbeBundle) -> List[Hypothesis]:
        """供报告「假设树」区块使用。"""
        return self._hypothesis_gen.generate(obs, bundle)

    def analyze(self, obs: ObservationContext, bundle: ProbeBundle) -> List[RootCause]:
        """路径层根因 + 置信度与证据边界标注。"""
        base = self._path_analyzer.analyze(bundle.business_probes)
        findings: List[BusinessRCAFinding] = []
        for c in base:
            disconfirmers: List[str] = []
            needs_cpe = False
            if c.cause_id == "BIZ-DNS-001" and obs.pc and obs.pc.dns_servers:
                disconfirmers.append("PC 已记录 DNS 服务器，若仅为上游失败需核对递归/分流策略")
            if c.cause_id in ("BIZ-TCP-001", "BIZ-TCP-TIMEOUT-001", "BIZ-TCP-REFUSED-001"):
                needs_cpe = not obs.cpe_evidence_available
                if obs.pc and obs.pc.proxy_enabled:
                    disconfirmers.append("本机系统代理已开启，建议核对是否影响探测或真实业务流量")
                if obs.cpe_evidence_available:
                    disconfirmers.append(
                        "已具备 CPE 证据：请结合隧道/策略路由结论判断 TCP 失败是否发生在 SD-WAN 域内"
                    )
            if c.cause_id == "BIZ-DNS-SPLIT-001":
                disconfirmers.append("对照结果已采集：可进一步比对 PC 网卡 DNS 与 SD-WAN DNS 策略")
            findings.append(
                BusinessRCAFinding(
                    cause=c,
                    disconfirmers=disconfirmers,
                    needs_cpe_evidence=needs_cpe,
                )
            )
        out: List[RootCause] = [f.as_root_cause() for f in findings]
        if obs.pc is None:
            out.insert(
                0,
                RootCause(
                    cause_id="BIZ-CONF-001",
                    title="分析置信度受限（未采集 PC 快照）",
                    description=(
                        "当前未纳入本机路由、DNS、代理等观测摘要，业务根因结论可能不完整。"
                        "建议使用默认开启的本机采集（`--collect-pc`）或深度诊断全量流程。"
                    ),
                    severity=Severity.INFO,
                    confidence=0.55,
                    evidence_refs=[obs.trace_id],
                    matched_rules=["BIZ-CONFIDENCE-BOUNDARY"],
                ),
            )
        logger.debug("BusinessRCAEngine: %d root cause(s)", len(out))
        return out


def build_observation_for_analysis(
    trace_id: str,
    pc_snapshot: Any,
    pc_data: dict,
    cpe_result: CollectorResult,
    topology: Optional[NetworkTopology],
) -> ObservationContext:
    """从深度诊断或独立 CLI 的上下文构造 ``ObservationContext``。"""
    pc = PCObservationSummary.from_snapshot_like(pc_snapshot or pc_data, trace_id)
    cpe_ok = bool(
        cpe_result.success
        and isinstance(cpe_result.data, dict)
        and cpe_result.data.get("cpe_configuration") is not None
    )
    node_id = topology.cpe_node_id if topology is not None else None
    return ObservationContext(
        trace_id=trace_id,
        pc=pc,
        cpe_evidence_available=cpe_ok,
        cpe_node_id=node_id,
    )


def build_probe_bundle_from_targeted(
    trace_id: str,
    targeted_probe: Optional[dict],
) -> Optional[ProbeBundle]:
    """从 ``targeted_probe`` 信封构造 ``ProbeBundle``；无业务行时返回 ``None``。"""
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return None
    if targeted_probe.get("status") not in ("ok", "partial"):
        return None
    data = targeted_probe.get("data") or {}
    rows = data.get("business_probes")
    if not rows or not isinstance(rows, list):
        return None
    raw = dict(data.get("raw_outputs") or {})
    return ProbeBundle(trace_id=trace_id, business_probes=list(rows), raw_outputs=raw)


def build_observation_standalone(trace_id: str, pc_snapshot: Any) -> ObservationContext:
    """独立 ``business-diagnose``：无 CPE 证据时的观测上下文。"""
    pc = PCObservationSummary.from_snapshot_like(pc_snapshot, trace_id)
    return ObservationContext(
        trace_id=trace_id,
        pc=pc,
        cpe_evidence_available=False,
        cpe_node_id=None,
    )
