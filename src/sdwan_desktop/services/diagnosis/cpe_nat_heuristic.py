"""CPE NAT inside 静态启发式是否适用于当前声明业务路径。

business-diagnose 联合场景：经 Overlay/隧道转发的业务在 CPE 上通常不对 PC 网段做源 NAT；
普通 Internet Underlay 出口业务仍须核对 NAT inside 覆盖（见产品门控文档 §5、§11）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.services.diagnosis.joint_overlay_datapath_gate import (
    compute_joint_overlay_datapath_gate,
)
from sdwan_desktop.services.diagnosis.raisecom_msg5200b_session import (
    is_raisecom_msg5200b_cpe,
)

logger = logging.getLogger(__name__)


def _business_joint_probe_context(targeted_probe: Optional[Dict[str, Any]]) -> bool:
    if not targeted_probe or not isinstance(targeted_probe, dict):
        return False
    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return False
    rows = data.get("business_probes")
    return isinstance(rows, list) and len(rows) > 0


def _pc_ip_from_topology(topology_dict: Optional[Dict[str, Any]]) -> Optional[str]:
    if not topology_dict:
        return None
    pc_id = topology_dict.get("pc_node_id")
    if not pc_id:
        return None
    for n in topology_dict.get("nodes") or []:
        if isinstance(n, dict) and n.get("id") == pc_id and n.get("type") == "pc":
            ip = (n.get("ip_address") or "").strip()
            return ip or None
    return None


def _raisecom_sdwan_overlay_config_intent(
    targeted_probe: Dict[str, Any],
    cpe: CpeConfiguration,
    topology_dict: Optional[Dict[str, Any]],
) -> bool:
    """声明域命中 url-group → 配置意图为 sdwan_overlay（默认不经 CPE NAT inside）。"""
    from sdwan_desktop.services.diagnosis.raisecom_msg5200b_url_group import (
        build_raisecom_msg5200b_url_group_analysis,
        probe_domain_from_targeted_data,
    )

    data = targeted_probe.get("data")
    if not isinstance(data, dict):
        return False
    domain = probe_domain_from_targeted_data(data)
    pc_ip = _pc_ip_from_topology(topology_dict)
    url_group = build_raisecom_msg5200b_url_group_analysis(
        domain=domain,
        targeted_data=data,
        cpe=cpe,
        pc_ip=pc_ip,
    )
    return bool(url_group and url_group.domain_matched)


def cpe_nat_inside_heuristic_applicable(
    *,
    cpe_config: Optional[CpeConfiguration],
    targeted_probe: Optional[Dict[str, Any]] = None,
    topology_dict: Optional[Dict[str, Any]] = None,
) -> bool:
    """是否应对 PC 快照主地址做 CPE NAT inside 静态比对。

    Returns:
        ``True``：应执行比对（可能产生 CPE-004）。
        ``False``：跳过 CPE-004（Overlay/隧道面为 SD-WAN 默认，不要求 PC 网段编入 NAT inside）。
    """
    if not cpe_config:
        return True
    if not _business_joint_probe_context(targeted_probe):
        return True

    tp = targeted_probe
    assert tp is not None

    if is_raisecom_msg5200b_cpe(cpe_config) and _raisecom_sdwan_overlay_config_intent(
        tp, cpe_config, topology_dict
    ):
        logger.debug(
            "CPE-004 跳过：5200B 声明域命中 url-group，配置意图 sdwan_overlay（默认不经 CPE NAT）"
        )
        return False

    gate = compute_joint_overlay_datapath_gate(tp, cpe_config, topology_dict)
    if gate.overlay_evidence_positive:
        logger.debug(
            "CPE-004 跳过：联合门控认定声明业务经 Overlay/隧道面（rule_case=%s）",
            gate.rule_case,
        )
        return False

    return True
