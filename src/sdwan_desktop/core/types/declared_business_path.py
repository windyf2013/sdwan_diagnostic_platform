"""声明业务路径分析（business-diagnose 联合 CPE）跨层契约。

产品规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md``（路径对账 §）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

ConfigIntent = Literal["internet_underlay", "sdwan_overlay", "unknown"]
ObservedPlane = Literal["underlay", "overlay", "unknown"]
ReconcileOutcome = Literal["match", "mismatch", "insufficient_evidence"]
ConfidenceTier = Literal["precise", "heuristic", "unverified"]
StepStatus = Literal["match", "miss", "not_applicable", "unknown"]


@dataclass(slots=True)
class MatchedUrlGroupInfo:
    """单 url-group 命中摘要（域在列表时）。"""

    name: str
    priority: int = 0
    security_ip_enabled: bool = False
    fwmark_hint: str = ""
    table_hint: str = ""
    policy_line_hint: str = ""
    url_match_mode: str = ""
    matched_pattern: str = ""


@dataclass(slots=True)
class PerGroupSecurityRow:
    """每组 security-ip 状态（报告附录）。"""

    group: str
    security_ip_enabled: bool
    pc_in_list: Optional[bool] = None


@dataclass(slots=True)
class UrlGroupAnalysis:
    """域命中 url-group 时 mandatory 分析块。"""

    domain: str
    matched_groups: List[MatchedUrlGroupInfo] = field(default_factory=list)
    effective_group: Optional[str] = None
    effective_selection_reason: str = ""
    per_group_security: List[PerGroupSecurityRow] = field(default_factory=list)
    policy_intent_one_liner: str = ""
    summary: str = ""
    link_protect_summary: str = ""
    domain_matched: bool = False


@dataclass(slots=True)
class PolicyChainStep:
    """策略链单跳：配置 | 运行 | 结论。"""

    stage_id: str
    config_status: StepStatus = "unknown"
    runtime_status: StepStatus = "unknown"
    config_excerpt: str = ""
    runtime_excerpt: str = ""
    narrative: str = ""


@dataclass(slots=True)
class ReachabilityAnalysis:
    """可达性阶段 S1/S2（Phase D）。"""

    s1_status: str = "unknown"
    s1_summary: str = ""
    s2_status: str = "unknown"
    s2_summary: str = ""
    primary_rule_case: str = ""
    next_hop_checked: str = ""


@dataclass(slots=True)
class PathReconcileResult:
    """期望配置意图 vs 运行面裁决。"""

    outcome: ReconcileOutcome = "insufficient_evidence"
    primary_rule_case: str = ""
    break_point: Optional[str] = None
    summary_for_delivery: str = ""


@dataclass(slots=True)
class DeclaredBusinessPathAnalysis:
    """5200B 声明业务路径分析单一事实源（联合 CPE）。"""

    status: str = "ok"
    config_intent: ConfigIntent = "unknown"
    observed_plane: ObservedPlane = "unknown"
    confidence: ConfidenceTier = "unverified"
    url_group_analysis: Optional[UrlGroupAnalysis] = None
    policy_chain_contrast: List[PolicyChainStep] = field(default_factory=list)
    reachability: ReachabilityAnalysis = field(default_factory=ReachabilityAnalysis)
    reconcile: PathReconcileResult = field(default_factory=PathReconcileResult)
    error: Optional[str] = None

    def to_template_dict(self) -> Dict[str, Any]:
        """模板 / topology JSON 序列化（snake_case 键）。"""
        payload: Dict[str, Any] = {
            "status": self.status,
            "config_intent": self.config_intent,
            "observed_plane": self.observed_plane,
            "confidence": self.confidence,
            "reconcile": asdict(self.reconcile),
            "policy_chain_contrast": {
                "steps": [asdict(s) for s in self.policy_chain_contrast],
                "break_point": self.reconcile.break_point,
                "summary_for_delivery": self.reconcile.summary_for_delivery,
            },
            "reachability": asdict(self.reachability),
        }
        if self.url_group_analysis is not None:
            ug = self.url_group_analysis
            payload["url_group_analysis"] = {
                "domain": ug.domain,
                "domain_matched": ug.domain_matched,
                "effective_group": ug.effective_group,
                "effective_selection_reason": ug.effective_selection_reason,
                "policy_intent_one_liner": ug.policy_intent_one_liner,
                "summary": ug.summary,
                "link_protect_summary": ug.link_protect_summary,
                "matched_groups": [asdict(g) for g in ug.matched_groups],
                "per_group_security": [asdict(r) for r in ug.per_group_security],
            }
        if self.error:
            payload["error"] = self.error
        return payload
