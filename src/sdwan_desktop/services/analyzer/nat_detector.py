"""
NAT 穿透检测辅助逻辑

负责检测 PC 流量是否匹配 CPE 的 NAT 规则，识别 NAT 不匹配导致的故障。
"""

import logging
from typing import List, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, NatRuleInfo
from sdwan_desktop.core.types.diagnosis import RootCause, Severity
from sdwan_desktop.services.topology.topology import NetworkTopology

logger = logging.getLogger(__name__)


class NatDetector:
    """NAT 穿透检测器"""

    def detect_nat_mismatch(
        self,
        topology: NetworkTopology,
        cpe_config: CpeConfiguration,
        pc_data: dict,
    ) -> List[RootCause]:
        """检测 NAT 不匹配问题 (CPE-004)

        Args:
            topology: 网络拓扑
            cpe_config: CPE 配置对象
            pc_data: PC 端采集数据

        Returns:
            识别出的根因列表
        """
        causes = []
        pc_ip = pc_data.get("primary_ip")
        
        if not pc_ip or not cpe_config.nat_rules:
            return causes

        # 检查 PC IP 是否在 NAT 规则的 Inside Address 范围内
        matched_nat = False
        for rule in cpe_config.nat_rules:
            if self._is_ip_in_rule(pc_ip, rule):
                matched_nat = True
                break

        if not matched_nat:
            causes.append(RootCause(
                cause_id="CPE-004",
                title="NAT 不匹配",
                description=(
                    f"PC 快照主地址 {pc_ip} 未匹配到任何已解析的 CPE NAT inside 规则（静态启发式）。"
                    " 若路径为 PC→上游路由/NAT→CPE，业务在 CPE 上常见不到 PC 私网源，"
                    "nf_conntrack 亦不应期望出现 PC 源；请用 CPE 外向会话源与上游 WAN 对照，"
                    "勿仅凭「未见 PC 源会话」断言本机 NAT 失效。"
                ),
                severity=Severity.WARNING,
                confidence=0.80,
                evidence_refs=[topology.pc_node_id, topology.cpe_node_id],
                matched_rules=["NAT-MATCHING-CHECK"],
            ))

        return causes

    def _is_ip_in_rule(self, ip: str, rule: NatRuleInfo) -> bool:
        """简化判断 IP 是否在 NAT 规则内
        
        实际应使用 ipaddress 模块进行子网匹配。
        """
        # 简化：直接比对字符串前缀或完全匹配
        inside_addr = rule.inside_addr.split("/")[0] if rule.inside_addr else ""
        return ip == inside_addr or ip.startswith(inside_addr.rsplit(".", 1)[0])
