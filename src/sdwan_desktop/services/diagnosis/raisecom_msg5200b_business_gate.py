"""Raisecom MSG5200B：business-diagnose 联合 Overlay 门控（5200B-only）。

规则：``docs/rules/product_features/raisecom_msg5200b_business_joint_gate.md``（L0–L5）。
实现委托：``raisecom_msg5200b_path_verdict.compute_raisecom_msg5200b_path_verdict``。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.diagnosis.joint_overlay_datapath_gate import (
    JointOverlayDatapathGate,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_path_verdict import (
    compute_raisecom_msg5200b_path_verdict,
)


def compute_raisecom_msg5200b_joint_overlay_gate(
    targeted_probe: Optional[Dict[str, Any]],
    cpe_configuration: Optional[CpeConfiguration],
    topology_dict: Optional[Dict[str, Any]],
) -> JointOverlayDatapathGate:
    """5200B 路径门控入口（L0–L5 聚合，已废除 D0 公网 DIP 硬否决）。"""
    return compute_raisecom_msg5200b_path_verdict(
        targeted_probe, cpe_configuration, topology_dict
    )
