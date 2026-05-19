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
        tunnels = cpe_config.vpn_tunnels

        active_tunnels = [t for t in tunnels if t.state == "up"]
        if active_tunnels:
            return self._bfd_followup(active_tunnels, cpe_config)

        explicitly_down = [t for t in tunnels if t.state == "down"]
        if explicitly_down:
            causes.append(RootCause(
                cause_id="CPE-002",
                title="VPN 隧道 Down",
                description="存在状态为 Down 的 SD-WAN/VXLAN 隧道，Overlay 可能不可用。",
                severity=Severity.CRITICAL,
                confidence=0.95,
                evidence_refs=self._tunnel_evidence_refs(cpe_config, explicitly_down),
                matched_rules=["TUNNEL-STATUS-CHECK"],
            ))
            return causes

        # running-config 仅有 unknown / 或未入库隧道记录时，用语义路由佐证转发面
        if self._overlay_datapath_looks_up(cpe_config):
            logger.info(
                "隧道未标记 up 或未解析，但 vxlan/策略路由表明 Overlay 转发面疑似可用，跳过 CPE-002"
            )
            return causes

        if not tunnels:
            causes.append(RootCause(
                cause_id="CPE-002",
                title="VPN 隧道 Down",
                description="未解析到隧道会话且未发现 Overlay 接口路由佐证，Overlay 网络不可用或无法确认。",
                severity=Severity.CRITICAL,
                confidence=0.85,
                evidence_refs=self._tunnel_evidence_refs(cpe_config, []),
                matched_rules=["TUNNEL-STATUS-CHECK"],
            ))
            return causes

        inconclusive = [
            t for t in tunnels
            if t.state in ("unknown", "init", "")
        ]
        causes.append(RootCause(
            cause_id="CPE-002-WARN",
            title="Overlay 隧道状态未知",
            description=(
                "已解析到隧道定义或会话，但缺少 link-detect/up 状态且路由侧未能确认 "
                "VXLAN 转发面，请核对 show link detect / BFD。"
            ),
            severity=Severity.WARNING,
            confidence=0.6,
            evidence_refs=self._tunnel_evidence_refs(cpe_config, inconclusive),
            matched_rules=["TUNNEL-STATUS-CHECK"],
        ))
        return causes

    def _bfd_followup(
        self,
        active_tunnels: List[VpnTunnelInfo],
        cpe_config: CpeConfiguration,
    ) -> List[RootCause]:
        causes = []
        bfd_down_count = 0
        for tunnel in active_tunnels:
            if self._is_bfd_down(tunnel):
                bfd_down_count += 1

        if bfd_down_count > 0:
            causes.append(RootCause(
                cause_id="OVERLAY-001",
                title="BFD 会话 Down",
                description=(
                    f"检测到 {bfd_down_count} 个活跃隧道的 BFD 会话异常，可能导致流量切换或丢包。"
                ),
                severity=Severity.WARNING,
                confidence=0.85,
                evidence_refs=[cpe_config.id],
                matched_rules=["BFD-SESSION-CHECK"],
            ))

        return causes

    def _overlay_datapath_looks_up(self, cpe: CpeConfiguration) -> bool:
        """根据路由表 / 策略路由原始输出推断 Overlay 转发面是否疑似可用。"""
        for route in cpe.routes:
            iface = (route.interface or "").lower()
            if iface.startswith("vxlan") and route.protocol in ("connected", "kernel", "static"):
                return True
        raw = cpe.raw_outputs or {}
        t99 = raw.get("diagnose:ip route show table 99", "") or ""
        if "vxlan" in t99.lower() and ("default" in t99.lower() or "via" in t99.lower()):
            return True
        return False

    def _tunnel_evidence_refs(
        self,
        cpe: CpeConfiguration,
        tunnels: List[VpnTunnelInfo],
    ) -> List[str]:
        """生成可读的证据引用（命令/片段线索）。"""
        refs: List[str] = [f"cpe:{cpe.hostname or cpe.id}"]
        for t in tunnels[:5]:
            if t.raw_block:
                refs.append("show running-config: tunnel …")
                break
        raw = cpe.raw_outputs or {}
        if raw.get("show link detect"):
            refs.append("show link detect")
        if raw.get("diagnose:ip route show table 99"):
            refs.append("diagnose:ip route show table 99")
        if any((r.interface or "").lower().startswith("vxlan") for r in cpe.routes):
            refs.append("show ip route (vxlan …)")
        return refs

    def _is_bfd_down(self, tunnel: VpnTunnelInfo) -> bool:
        """判断 BFD 是否 Down（简化实现）"""
        # 在实际解析器中，可能需要解析 show sdwan bfd sessions 的详细输出
        # 这里暂时返回 False，待解析器增强后完善
        return False
