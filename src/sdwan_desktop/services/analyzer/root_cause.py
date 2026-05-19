"""
根因分析引擎 - 深度诊断核心逻辑

根据 Sprint 4 阶段 4.5 规范实现，覆盖 CPE 不可达、隧道 Down、策略路由失效等故障场景。
遵循 SDWAN_SPEC.md §3.3 诊断相关契约
"""

import logging
import re
from typing import Any, Dict, List, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.core.types.diagnosis import RootCause, Severity
from sdwan_desktop.services.analyzer.overlay_analyzer import OverlayAnalyzer
from sdwan_desktop.services.analyzer.nat_detector import NatDetector
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.diagnosis.business_rca_engine import (
    BusinessRCAEngine,
    build_observation_for_analysis,
    build_probe_bundle_from_targeted,
)
from sdwan_desktop.services.reporter.joint_commercial_delivery import (
    joint_datapath_evidence_from_targeted_probe,
    path_beyond_tunnel_likely,
)
from sdwan_desktop.services.topology.topology import NetworkTopology
from sdwan_desktop.tools.registry.decorator import pure_function

logger = logging.getLogger(__name__)

_SEVERITY_DISPLAY_RANK = {
    Severity.CRITICAL: 0,
    Severity.ERROR: 1,
    Severity.WARNING: 2,
    Severity.INFO: 3,
}


def sort_root_causes_for_display(causes: List[RootCause]) -> None:
    """按严重度（ERROR 优先于 WARNING 等）再按置信度降序排列，供报告与 JSON 一致展示。"""
    causes.sort(
        key=lambda c: (
            _SEVERITY_DISPLAY_RANK.get(c.severity, 9),
            -round(float(c.confidence or 0.0), 6),
            c.cause_id or "",
        )
    )


class RootCauseEngine:
    """根因分析引擎

    结合网络拓扑和 CPE 配置，执行深度诊断规则，识别根因并生成建议。
    """

    def __init__(self):
        self.overlay_analyzer = OverlayAnalyzer()
        self.nat_detector = NatDetector()

    @pure_function
    def analyze(
        self,
        topology: NetworkTopology,
        cpe_result: CollectorResult,
        pc_data: dict,
        targeted_probe: Optional[Dict[str, Any]] = None,
        trace_id: str = "",
        pc_snapshot: Any = None,
        overlay_policy_flow: Optional[Dict[str, Any]] = None,
    ) -> List[RootCause]:
        """执行根因分析

        Args:
            topology: 构建好的网络拓扑
            cpe_result: CPE 采集结果（包含 CpeConfiguration）
            pc_data: PC 端采集数据（用于对比路由和 NAT）
            targeted_probe: 拓扑后主动探测结果信封 ``{status, data, error}``；缺失时行为与旧版一致。
            trace_id: 追踪 ID（用于业务 RCA 证据引用）。
            pc_snapshot: 原始 PC 快照对象（优先于 ``pc_data`` 构造观测摘要）。
            overlay_policy_flow: ``run_overlay_policy_flow_step`` 产出信封；用于与 CPE-003/CPE-004 启发式对账。

        Returns:
            识别出的根因列表
        """
        causes = []

        # 1. 检查 CPE 是否可达 (CPE-001)
        if not cpe_result.success:
            causes.append(self._create_cpe_unreachable(cpe_result))
            causes.extend(
                self._business_causes_from_probe(
                    targeted_probe, trace_id, cpe_result, topology, pc_snapshot, pc_data
                )
            )
            sort_root_causes_for_display(causes)
            return causes  # 如果 CPE 不可达，后续分析无法进行

        cpe_config = cpe_result.data.get("cpe_configuration")
        if not cpe_config:
            logger.warning("CPE 配置解析失败，无法进行深度分析")
            causes.extend(
                self._business_causes_from_probe(
                    targeted_probe, trace_id, cpe_result, topology, pc_snapshot, pc_data
                )
            )
            sort_root_causes_for_display(causes)
            return causes

        # 2. 检查 Overlay 状态 (CPE-002, OVERLAY-001)
        overlay_causes = self.overlay_analyzer.check_overlay_status(cpe_config)
        causes.extend(overlay_causes)

        session_evidence = self._conntrack_evidence_from_probe(targeted_probe)

        # 3. 检查 NAT 穿透 (CPE-004)
        nat_causes = self.nat_detector.detect_nat_mismatch(topology, cpe_config, pc_data)
        causes.extend(nat_causes)

        # 4. 检查策略路由 (CPE-003)
        policy_causes = self._check_policy_routing(topology, cpe_config, pc_data)
        causes.extend(policy_causes)

        causes.extend(self._link_protect_causes_from_probe(targeted_probe, topology))
        causes.extend(
            self._business_causes_from_probe(
                targeted_probe, trace_id, cpe_result, topology, pc_snapshot, pc_data
            )
        )
        self._apply_session_evidence(causes, session_evidence)
        self._apply_trace_evidence(causes, targeted_probe, cpe_config, topology)
        self._reconcile_policy_nat_with_tunnel_datapath(causes, targeted_probe)
        self._reconcile_causes_when_targeted_business_ok(targeted_probe, causes)
        apply_overlay_policy_flow_to_causes(causes, overlay_policy_flow)

        sort_root_causes_for_display(causes)
        logger.info(f"根因分析完成，共识别出 {len(causes)} 个潜在问题")
        return causes

    def _conntrack_evidence_from_probe(
        self,
        targeted_probe: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """从 targeted probe 提取 nf_conntrack 证据摘要。"""
        if not targeted_probe or targeted_probe.get("status") not in ("ok", "partial"):
            return {"enabled": False}
        data = targeted_probe.get("data") or {}
        raw_out = data.get("raw_outputs") or {}
        conntrack_lines: List[str] = []
        matched_ips: List[str] = []
        for k, v in raw_out.items():
            if not str(k).startswith("diagnose:nf_conntrack grep "):
                continue
            ip = str(k).split("diagnose:nf_conntrack grep ", 1)[-1].strip()
            if ip:
                matched_ips.append(ip)
            for line in str(v or "").splitlines():
                if line.strip():
                    conntrack_lines.append(line.strip())
        if not matched_ips:
            matched_ips = list(data.get("biz_target_ips") or [])
        state_counts: Dict[str, int] = {}
        for line in conntrack_lines:
            m = re.search(
                r"\b(TIME_WAIT|ESTABLISHED|SYN_SENT|SYN_RECV|FIN_WAIT|FIN_WAIT1|FIN_WAIT2|CLOSE_WAIT|LAST_ACK|CLOSED|UNREPLIED|ASSURED)\b",
                line,
                re.IGNORECASE,
            )
            if m:
                key = m.group(1).upper()
                state_counts[key] = state_counts.get(key, 0) + 1
        has_established = bool(
            state_counts.get("ESTABLISHED") or state_counts.get("ASSURED")
        )
        closing_states = (
            state_counts.get("TIME_WAIT", 0)
            + state_counts.get("CLOSE_WAIT", 0)
            + state_counts.get("LAST_ACK", 0)
            + state_counts.get("CLOSED", 0)
            + state_counts.get("FIN_WAIT", 0)
            + state_counts.get("FIN_WAIT1", 0)
            + state_counts.get("FIN_WAIT2", 0)
        )
        has_closing_residual_pattern = (
            len(conntrack_lines) > 0 and not has_established and closing_states > 0
        )
        has_only_syn_or_unreplied = (
            len(conntrack_lines) > 0
            and not has_established
            and not has_closing_residual_pattern
        )
        return {
            "enabled": bool(matched_ips),
            "matched_ips": matched_ips,
            "line_count": len(conntrack_lines),
            "state_counts": state_counts,
            "has_progress_state": has_established,
            "has_closing_residual_pattern": has_closing_residual_pattern,
            "has_only_syn_or_unreplied": has_only_syn_or_unreplied,
        }

    def _apply_session_evidence(self, causes: List[RootCause], session: Dict[str, Any]) -> None:
        """将会话表证据并入根因文案与置信度。"""
        if not session.get("enabled"):
            return
        ips = ", ".join(session.get("matched_ips") or [])
        states = session.get("state_counts") or {}
        state_text = ", ".join(f"{k}:{v}" for k, v in states.items()) if states else "none"
        line_count = int(session.get("line_count") or 0)
        has_progress = bool(session.get("has_progress_state"))
        only_syn_or_unreplied = bool(session.get("has_only_syn_or_unreplied"))
        closing_residual = bool(session.get("has_closing_residual_pattern"))
        for cause in causes:
            if cause.cause_id in ("CPE-003", "CPE-004"):
                if has_progress:
                    cause.confidence = min(cause.confidence, 0.62)
                    cause.description += (
                        f" 会话证据：目标IP({ips})命中 {line_count} 条，状态[{state_text}]，"
                        "存在已建立/可推进会话，需谨慎判断为本地策略或NAT根因。"
                    )
                elif line_count == 0:
                    # 零命中不能反推 NAT/策略：grep 按业务目的 IP；PC→上游 NAT→CPE 时 CPE 上常见不到 PC 私网源。
                    cause.confidence = min(cause.confidence, 0.66)
                    cause.description += (
                        f" 会话证据：按业务目的地址 grep 的 nf_conntrack 在采样窗口内对 {ips} 零命中。"
                        " 这**不能**证明「NAT 不匹配」或「策略必未命中」：可能为会话过期/探测时机不同步，"
                        "或路径经上游 NAT 后 CPE 观察面与 PC 快照源不一致。"
                    )
                elif closing_residual:
                    cause.confidence = min(cause.confidence, 0.64)
                    cause.description += (
                        f" 会话证据：目标IP({ips})命中 {line_count} 条，状态[{state_text}]；"
                        "主要为收尾态（如 TIME_WAIT），常见于探测会话刚结束后的残留，"
                        "不宜单独作为业务失败或对端不响应的强证据。"
                    )
                elif only_syn_or_unreplied:
                    cause.confidence = min(cause.confidence, 0.70)
                    cause.description += (
                        f" 会话证据：目标IP({ips})命中 {line_count} 条，状态[{state_text}]，"
                        "未见明确已建立会话，更偏向上游/远端不响应或中间路径黑洞。"
                    )
            if cause.cause_id.startswith("BIZ-TCP"):
                if line_count == 0:
                    cause.confidence = min(max(cause.confidence, 0.55), 0.72)
                    cause.description += (
                        f" 会话证据：目的 {ips} 在采样窗口内未见 conntrack 命中；"
                        " 更宜结合上游 NAT 与采样时刻解读，不宜单独等同于「策略/NAT 未匹配前即失败」。"
                    )
                elif closing_residual:
                    cause.confidence = min(cause.confidence, 0.62)
                    cause.description += (
                        f" 会话证据：目标IP({ips})状态[{state_text}]以收尾态为主，"
                        "可能为探测结束后 conntrack 残留，不宜单独支撑 TCP 超时根因。"
                    )
                elif only_syn_or_unreplied:
                    cause.confidence = max(cause.confidence, 0.75)
                    cause.description += (
                        f" 会话证据：目标IP({ips})有会话但状态[{state_text}]，"
                        "更符合中间路径丢弃或对端无响应。"
                    )
                elif has_progress:
                    cause.confidence = min(cause.confidence, 0.60)
                    cause.description += (
                        f" 会话证据：目标IP({ips})存在状态推进[{state_text}]，"
                        "仅凭 tcp timeout 不能直接判定 SD-WAN 域内不可达。"
                    )

    def _apply_trace_evidence(
        self,
        causes: List[RootCause],
        targeted_probe: Optional[Dict[str, Any]],
        cpe_config: Any,
        topology: NetworkTopology,
    ) -> None:
        """将 PC 侧 ``business_probes[].trace`` 旁证并入 BIZ-TCP 根因（与 overlay 门控、拓扑着色同源）。"""
        from sdwan_desktop.services.diagnosis.business_trace_evidence import (
            analyze_business_trace_evidence,
        )

        top_d = topology.to_dict() if topology is not None and hasattr(topology, "to_dict") else None
        trace_ev = analyze_business_trace_evidence(targeted_probe, cpe_config, top_d)
        if not trace_ev.trace_available:
            return
        note_base = trace_ev.narrative_hint or "已采集 traceroute 跳表"
        for cause in causes:
            if not cause.cause_id.startswith("BIZ-TCP"):
                continue
            if trace_ev.egress_past_cpe:
                cause.confidence = max(float(cause.confidence), 0.72)
                extra = (
                    f" 路径追踪旁证：{note_base}。"
                    "更符合故障发生在 CPE/SD-WAN 域外或对端路径，不宜单独将 CPE Underlay 节点判为断点。"
                )
                if extra not in cause.description:
                    cause.description += extra
            elif trace_ev.overlay_hop_observed:
                extra = f" 路径追踪旁证：{note_base}（命中隧道/Overlay 相关跳）。"
                if extra not in cause.description:
                    cause.description += extra

    def _targeted_business_probes_all_ok(
        self, targeted_probe: Optional[Dict[str, Any]]
    ) -> bool:
        """与业务联合报告中 ``business_failure_stage==ok`` 的语义对齐（拓扑后信封）。

        仅校验 **DNS + TCP**；忽略 ``trace``（traceroute），与 ``targeted_probe_business_rows_all_ok`` 一致。
        """
        if not targeted_probe or targeted_probe.get("status") not in ("ok", "partial"):
            return False
        data = targeted_probe.get("data") or {}
        rows = data.get("business_probes")
        if not isinstance(rows, list):
            return False
        for row in rows:
            if not isinstance(row, dict):
                continue
            dns = row.get("dns") if isinstance(row.get("dns"), dict) else {}
            if dns.get("status") not in ("ok",):
                return False
            tcp_rows = row.get("tcp") if isinstance(row.get("tcp"), list) else []
            for t in tcp_rows:
                if not isinstance(t, dict):
                    continue
                if t.get("status") != "ok":
                    return False
                td = t.get("data") if isinstance(t.get("data"), dict) else {}
                if td.get("port_open") is False:
                    return False
        return bool(rows)

    def _reconcile_causes_when_targeted_business_ok(
        self, targeted_probe: Optional[Dict[str, Any]], causes: List[RootCause]
    ) -> None:
        """拓扑后业务探测已全部成功时，下调配置启发式严重度并补充与观测一致的说明。"""
        if not self._targeted_business_probes_all_ok(targeted_probe):
            return
        policy_note = (
            "【与本机/拓扑后探测一致】声明目标在业务探测行中已达通；此处「策略未命中」来自 **PC 快照主地址** "
            "与 CPE ``sdwan_policies.source`` 的**启发式前缀比对**，不等价于转发面抓包结论（可能走默认路由、"
            "其它源 NAT、或策略以网段表述与快照主地址不一致）。请用 conntrack 源 IP 与策略表人工复核。"
        )
        nat_note = (
            "【与本机/拓扑后探测一致】声明目标已达通；NAT 不一致提示基于快照与配置解析的静态比对，"
            "请与现网会话记录交叉验证。"
        )
        for c in causes:
            if c.cause_id == "CPE-003" and c.severity in (Severity.ERROR, Severity.WARNING):
                if c.severity == Severity.ERROR:
                    c.severity = Severity.WARNING
                c.title = "PC 与 SD-WAN 策略源前缀未匹配（启发式；业务探测显示目标已达通）"
                if policy_note not in c.description:
                    c.description = f"{c.description}\n{policy_note}"
            elif c.cause_id == "CPE-004" and c.severity in (Severity.ERROR, Severity.WARNING):
                if c.severity == Severity.ERROR:
                    c.severity = Severity.WARNING
                c.title = "PC 网段未覆盖 CPE NAT inside（启发式；业务探测显示目标已达通）"
                if nat_note not in c.description:
                    c.description = f"{c.description}\n{nat_note}"

    def _business_causes_from_probe(
        self,
        targeted_probe: Optional[Dict[str, Any]],
        trace_id: str,
        cpe_result: CollectorResult,
        topology: NetworkTopology,
        pc_snapshot: Any,
        pc_data: dict,
    ) -> List[RootCause]:
        """从拓扑后信封中的 ``business_probes`` 经 ``BusinessRCAEngine`` 融合业务层根因。"""
        tid = trace_id or "unknown-trace"
        bundle = build_probe_bundle_from_targeted(tid, targeted_probe)
        if bundle is None:
            return []
        obs = build_observation_for_analysis(tid, pc_snapshot, pc_data, cpe_result, topology)
        return BusinessRCAEngine().analyze(obs, bundle)

    def _link_protect_causes_from_probe(
        self,
        targeted_probe: Optional[Dict[str, Any]],
        topology: NetworkTopology,
    ) -> List[RootCause]:
        """根据 ``show link-protect status`` 探测输出补充根因（Raisecom 等）。"""
        if not targeted_probe or targeted_probe.get("status") not in ("ok", "partial"):
            return []
        data = targeted_probe.get("data") or {}
        raw_out = data.get("raw_outputs") or {}
        raw = raw_out.get("show link-protect status") or ""
        if not str(raw).strip():
            return []
        if not re.search(r"current\s+action\s+status\s*:\s*down\b", str(raw), re.IGNORECASE):
            return []
        refs: List[str] = []
        if topology.cpe_node_id:
            refs.append(topology.cpe_node_id)
        return [
            RootCause(
                cause_id="RAISECOM-LINK-PROT-001",
                title="链路保护组存在接口 Down",
                description=(
                    "拓扑后探测 ``show link-protect status`` 显示某保护组当前动作接口为 Down，"
                    "业务路径可能已切换或不可用，请结合 Underlay 与 VXLAN 路由核查。"
                ),
                severity=Severity.WARNING,
                confidence=0.72,
                evidence_refs=refs,
                matched_rules=["LINK-PROTECT-STATUS-CHECK"],
            )
        ]

    def _reconcile_policy_nat_with_tunnel_datapath(
        self, causes: List[RootCause], targeted_probe: Optional[Dict[str, Any]]
    ) -> None:
        """隧道 ICMP 与 conntrack 形态与「策略/NAT 启发式」对齐，避免与拓扑隧道叙述矛盾。"""
        ev = joint_datapath_evidence_from_targeted_probe(targeted_probe)
        if ev is None:
            return
        # CPE-003 与 CPE-004 须分述：后者与 sdwan_policies 无关，避免在 NAT 卡片上误贴策略源话术。
        note_pbt_policy = (
            "【与隧道/会话观测对齐】隧道对端 ICMP 全通，且 nf_conntrack 对业务目的地址呈 SYN/UNREPLIED（未见 ESTABLISHED），"
            "更符合**对端以远或目的路径**类问题；此处「PC 与 sdwan_policies.source 前缀不一致」为**配置面对账启发式**，"
            "**不应**解读为整条策略路由/fwmark 选路或隧道转发面失效。"
        )
        note_pbt_nat = (
            "【与隧道/会话观测对齐】隧道对端 ICMP 全通，且 nf_conntrack 对业务目的地址呈 SYN/UNREPLIED（未见 ESTABLISHED），"
            "更符合**对端以远或目的路径**类问题；此处「PC 网段未编入 CPE NAT inside」为**配置面对账启发式**，"
            "**不应**解读为 CPE 未转发或未走隧道/Overlay 面。"
        )
        note_ct = (
            "【与隧道/会话观测对齐】隧道对端 ICMP 全通，且 CPE 上已采集到发往业务目的地址的 conntrack 行，"
            "说明业务报文已进入本机 netfilter 观测面；「策略源未命中」**不能**单独否定实际选路已走隧道/Overlay。"
        )
        title_cpe003_pbt = "PC 与 SD-WAN 策略源前缀未匹配（启发式；隧道/会话支持对侧路径）"
        title_cpe004_pbt = "PC 网段未覆盖 CPE NAT inside（启发式；隧道/会话支持对侧路径）"
        title_cpe003_ct = "PC 与 SD-WAN 策略源前缀未匹配（启发式；CPE 已有目的地址会话）"

        if path_beyond_tunnel_likely(ev):
            for c in causes:
                if c.cause_id not in ("CPE-003", "CPE-004"):
                    continue
                if c.severity not in (Severity.ERROR, Severity.WARNING):
                    continue
                c.severity = Severity.WARNING
                if c.cause_id == "CPE-003":
                    note = note_pbt_policy
                    c.title = title_cpe003_pbt
                else:
                    note = note_pbt_nat
                    c.title = title_cpe004_pbt
                if note not in c.description:
                    c.description = f"{c.description}\n{note}"
        elif ev.tunnel_peers_all_icmp_ok and ev.conntrack_line_count > 0:
            for c in causes:
                if c.cause_id != "CPE-003" or c.severity not in (Severity.ERROR, Severity.WARNING):
                    continue
                c.severity = Severity.WARNING
                c.title = title_cpe003_ct
                if note_ct not in c.description:
                    c.description = f"{c.description}\n{note_ct}"

    def _create_cpe_unreachable(self, cpe_result: CollectorResult) -> RootCause:
        """创建 CPE 不可达根因 (CPE-001)"""
        return RootCause(
            cause_id="CPE-001",
            title="CPE 设备不可达",
            description=f"无法通过 SSH/TELNET 连接到 CPE 设备。错误信息: {cpe_result.error_message}",
            severity=Severity.CRITICAL,
            confidence=0.95,
            evidence_refs=[],  # CollectorResult 没有 id 字段
            matched_rules=["CPE-CONNECTIVITY-CHECK"],
        )

    def _check_policy_routing(
        self,
        topology: NetworkTopology,
        cpe_config: CpeConfiguration,
        pc_data: dict,
    ) -> List[RootCause]:
        """检查策略路由是否生效 (CPE-003)

        验证 PC 的流量是否能正确匹配 CPE 的 SD-WAN 策略。
        """
        causes = []
        pc_ip = pc_data.get("primary_ip")
        if not pc_ip or not cpe_config.sdwan_policies:
            # 如果没有策略，但 PC 有 IP，且没有默认路由或其他保障，可能存在问题
            # 这里简化：如果没策略但有隧道，通常意味着流量走默认或丢弃
            if cpe_config.vpn_tunnels:
                causes.append(RootCause(
                    cause_id="CPE-003",
                    title="策略路由未生效",
                    description=(
                        "[启发式] 将 PC 采集的 primary_ip 与 CPE sdwan_policies.source 做前缀级匹配（非 ipaddress "
                        "精确包含判断）；未命中则提示可能未走策略域。"
                        f"当前：PC 地址 {pc_ip} 未匹配到任何有效的 SD-WAN 策略（共 0 条），"
                        "流量可能走默认路由或丢弃。"
                    ),
                    severity=Severity.WARNING,
                    confidence=0.80,
                    evidence_refs=[topology.pc_node_id, topology.cpe_node_id],
                    matched_rules=["POLICY-MATCHING-CHECK"],
                ))
            return causes

        # 简单逻辑：检查是否有针对 PC 网段的策略
        has_matching_policy = False
        for policy in cpe_config.sdwan_policies:
            # 实际应使用 ipaddress 模块进行子网匹配
            if policy.source == "any":
                has_matching_policy = True
                break
            # 简化前缀匹配
            source_prefix = policy.source.split("/")[0] if "/" in policy.source else policy.source
            if pc_ip.startswith(source_prefix.rsplit(".", 1)[0]):
                has_matching_policy = True
                break

        if not has_matching_policy:
            causes.append(RootCause(
                cause_id="CPE-003",
                title="策略路由未生效",
                description=(
                    "[启发式] 将 PC 采集的 primary_ip 与 CPE sdwan_policies.source 做前缀级匹配（非 ipaddress "
                    "精确包含判断）；未命中则提示可能未走策略域。"
                    f"当前：PC 地址 {pc_ip} 未匹配到任何有效的 SD-WAN 策略，流量可能走默认路由或丢弃。"
                ),
                severity=Severity.WARNING,
                confidence=0.80,
                evidence_refs=[topology.pc_node_id, topology.cpe_node_id],
                matched_rules=["POLICY-MATCHING-CHECK"],
            ))

        return causes


def apply_overlay_policy_flow_to_causes(
    causes: List[RootCause],
    overlay_policy_flow: Optional[Dict[str, Any]],
) -> None:
    """在已生成 Overlay/策略证据链后：弱化与其明显矛盾的 CPE-003/CPE-004（ERROR 或 WARNING）。"""
    if not causes or not isinstance(overlay_policy_flow, dict):
        return
    if overlay_policy_flow.get("status") not in ("ok", "partial"):
        return
    data = overlay_policy_flow.get("data")
    if not isinstance(data, dict):
        return
    tags = [str(t).lower() for t in (data.get("scenario_tags") or [])]
    notes = " ".join(str(x) for x in (data.get("probe_evidence_notes") or [])).lower()
    blob = notes + " " + " ".join(tags)
    if not any(t in tags for t in ("vxlan", "l2tp", "ipsec")):
        return
    if not any(k in blob for k in ("fwmark", "ip rule", "mangle", "ipset", "vxlan", "l2tp", "ipsec")):
        return
    note = (
        "【与 Overlay/策略证据链对齐】报告已归纳 vxlan/隧道面及典型 MARK→ip rule→多路由表 等组件；"
        "「PC primary 未编入 sdwan_policies / NAT inside」仅为与**快照主地址**的静态比对，"
        "必须与 conntrack 源、上游 NAT 及业务接口交叉验证，**不得**单独等同于策略路由未生效。"
    )
    title_cpe003_ov = "PC 与 SD-WAN 策略源前缀未匹配（启发式；Overlay/策略证据链已对账）"
    title_cpe004_ov = "PC 网段未覆盖 CPE NAT inside（启发式；Overlay/策略证据链已对账）"
    for c in causes:
        if c.cause_id not in ("CPE-003", "CPE-004") or c.severity not in (
            Severity.ERROR,
            Severity.WARNING,
        ):
            continue
        c.severity = Severity.WARNING
        if c.cause_id == "CPE-003":
            c.title = title_cpe003_ov
        else:
            c.title = title_cpe004_ov
        if note not in c.description:
            c.description = f"{c.description}\n{note}"
