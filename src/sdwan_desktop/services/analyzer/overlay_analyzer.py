"""
Overlay 状态分析辅助逻辑

负责检测 VPN 隧道状态和 BFD 会话健康度。
"""

import logging
from typing import List

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, VpnTunnelInfo
from sdwan_desktop.core.types.diagnosis import RootCause, Severity

logger = logging.getLogger(__name__)


class OverlayAnalyzer:
    """Overlay 状态分析器"""

    def check_overlay_status(self, cpe_config: CpeConfiguration) -> List[RootCause]:
        """检查 Overlay 链路状态

        Args:
            cpe_config: CPE 配置对象

        Returns:
            识别出的根因列表
        """
        causes = []
        
        # 1. 检查是否有活跃的隧道 (CPE-002)
        active_tunnels = [t for t in cpe_config.vpn_tunnels if t.state == "up"]
        if not active_tunnels:
            causes.append(RootCause(
                cause_id="CPE-002",
                title="VPN 隧道 Down",
                description="所有 SD-WAN 隧道均处于非活跃状态，Overlay 网络不可用。",
                severity=Severity.CRITICAL,
                confidence=0.95,
                evidence_refs=[cpe_config.id],
                matched_rules=["TUNNEL-STATUS-CHECK"],
            ))
            return causes

        # 2. 检查 BFD 会话状态 (OVERLAY-001)
        # 简化逻辑：如果隧道是 up 的，但 BFD 状态未知或 down，则报警
        bfd_down_count = 0
        for tunnel in active_tunnels:
            # 假设在 metadata 或 state 中有 BFD 信息，这里根据 spec 简化处理
            # 实际解析器可能需要提取更详细的 BFD 状态
            if self._is_bfd_down(tunnel):
                bfd_down_count += 1

        if bfd_down_count > 0:
            causes.append(RootCause(
                cause_id="OVERLAY-001",
                title="BFD 会话 Down",
                description=f"检测到 {bfd_down_count} 个活跃隧道的 BFD 会话异常，可能导致流量切换或丢包。",
                severity=Severity.WARNING,
                confidence=0.85,
                evidence_refs=[cpe_config.id],
                matched_rules=["BFD-SESSION-CHECK"],
            ))

        return causes

    def _is_bfd_down(self, tunnel: VpnTunnelInfo) -> bool:
        """判断 BFD 是否 Down（简化实现）"""
        # 在实际解析器中，可能需要解析 show sdwan bfd sessions 的详细输出
        # 这里暂时返回 False，待解析器增强后完善
        return False
