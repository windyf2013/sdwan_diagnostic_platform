"""
根因分析引擎 - 深度诊断核心逻辑

根据 Sprint 4 阶段 4.5 规范实现，覆盖 CPE 不可达、隧道 Down、策略路由失效等故障场景。
遵循 SDWAN_SPEC.md §3.3 诊断相关契约
"""

import logging
from typing import List, Optional

from sdwan_desktop.core.types.cpe_config import CpeConfiguration
from sdwan_desktop.core.types.diagnosis import RootCause, Severity
from sdwan_desktop.services.analyzer.overlay_analyzer import OverlayAnalyzer
from sdwan_desktop.services.analyzer.nat_detector import NatDetector
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.topology.topology import NetworkTopology
from sdwan_desktop.tools.registry.decorator import pure_function

logger = logging.getLogger(__name__)


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
    ) -> List[RootCause]:
        """执行根因分析

        Args:
            topology: 构建好的网络拓扑
            cpe_result: CPE 采集结果（包含 CpeConfiguration）
            pc_data: PC 端采集数据（用于对比路由和 NAT）

        Returns:
            识别出的根因列表
        """
        causes = []

        # 1. 检查 CPE 是否可达 (CPE-001)
        if not cpe_result.success:
            causes.append(self._create_cpe_unreachable(cpe_result))
            return causes  # 如果 CPE 不可达，后续分析无法进行

        cpe_config = cpe_result.data.get("cpe_configuration")
        if not cpe_config:
            logger.warning("CPE 配置解析失败，无法进行深度分析")
            return causes

        # 2. 检查 Overlay 状态 (CPE-002, OVERLAY-001)
        overlay_causes = self.overlay_analyzer.check_overlay_status(cpe_config)
        causes.extend(overlay_causes)

        # 3. 检查 NAT 穿透 (CPE-004)
        nat_causes = self.nat_detector.detect_nat_mismatch(topology, cpe_config, pc_data)
        causes.extend(nat_causes)

        # 4. 检查策略路由 (CPE-003)
        policy_causes = self._check_policy_routing(topology, cpe_config, pc_data)
        causes.extend(policy_causes)

        logger.info(f"根因分析完成，共识别出 {len(causes)} 个潜在问题")
        return causes

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
                    description=f"PC 地址 {pc_ip} 未匹配到任何有效的 SD-WAN 策略（共 0 条），流量可能走默认路由或丢弃。",
                    severity=Severity.ERROR,
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
                description=f"PC 地址 {pc_ip} 未匹配到任何有效的 SD-WAN 策略，流量可能走默认路由或丢弃。",
                severity=Severity.ERROR,
                confidence=0.80,
                evidence_refs=[topology.pc_node_id, topology.cpe_node_id],
                matched_rules=["POLICY-MATCHING-CHECK"],
            ))

        return causes
