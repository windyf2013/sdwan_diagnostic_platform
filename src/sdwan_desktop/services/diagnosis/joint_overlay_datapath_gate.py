"""联合业务诊断：Overlay/隧道呈现门控（跨厂商分发入口）。

项目规则：``docs/rules/THREE_FLOWS_PRODUCT_POSITIONING.md``。
5200B 专章：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration

EvidenceTier = Literal["precise", "heuristic", "underlay_only"]
EgressShape = Literal["", "wan_gateway", "early_public"]


@dataclass(frozen=True, slots=True)
class JointOverlayDatapathGate:
    """联合报告：Overlay 条带、cpe→hub 链路行与根因过滤门控（presentation 只读）。"""

    show_overlay_tunnel_strip: bool
    overlay_evidence_positive: bool
    rule_case: str
    datapath_banner: str
    joint_overlay_topology_note: str
    evidence_tier: EvidenceTier = "underlay_only"
    egress_shape: EgressShape = ""
    url_group_supplement: str = ""
    presentation_suppress_detail: str = ""

    @property
    def show_business_flow_overlay(self) -> bool:
        """与 ``show_overlay_tunnel_strip`` 同源（分层拓扑 Overlay + cpe→hub）。"""
        return self.show_overlay_tunnel_strip


def compute_joint_overlay_datapath_gate(
    targeted_probe: Optional[Dict[str, Any]],
    cpe_configuration: Optional[CpeConfiguration],
    topology_dict: Optional[Dict[str, Any]],
) -> JointOverlayDatapathGate:
    """按厂商分发至 5200B 专码或通用回退。"""
    from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
        is_raisecom_msg5200b_cpe,
    )

    if is_raisecom_msg5200b_cpe(cpe_configuration):
        from sdwan_desktop.services.diagnosis.raisecom_msg5200b_business_gate import (
            compute_raisecom_msg5200b_joint_overlay_gate,
        )

        return compute_raisecom_msg5200b_joint_overlay_gate(
            targeted_probe, cpe_configuration, topology_dict
        )

    from sdwan_desktop.services.diagnosis.generic_joint_overlay_gate import (
        compute_generic_joint_overlay_gate,
    )

    return compute_generic_joint_overlay_gate(
        targeted_probe, cpe_configuration, topology_dict
    )
