"""OverlayAnalyzer：隧道解析与路由佐证组合逻辑。"""

import pytest

from sdwan_desktop.core.types.cpe_config import CpeConfiguration, RouteEntry, VpnTunnelInfo
from sdwan_desktop.services.analyzer.overlay_analyzer import OverlayAnalyzer


@pytest.fixture
def analyzer() -> OverlayAnalyzer:
    return OverlayAnalyzer()


def test_unknown_tunnel_with_vxlan_route_skips_critical(analyzer: OverlayAnalyzer) -> None:
    cfg = CpeConfiguration(
        hostname="cpe",
        vpn_tunnels=[
            VpnTunnelInfo(remote_ip="5.0.1.1", state="unknown", type="vxlan", local_color="tunnel1_5"),
        ],
        routes=[
            RouteEntry(
                destination="8.1.3.0/30",
                interface="vxlan5",
                protocol="connected",
                metric=0,
            ),
        ],
    )
    assert analyzer.check_overlay_status(cfg) == []


def test_no_tunnel_no_datapath_still_critical(analyzer: OverlayAnalyzer) -> None:
    cfg = CpeConfiguration(hostname="cpe", vpn_tunnels=[], routes=[])
    causes = analyzer.check_overlay_status(cfg)
    assert len(causes) == 1
    assert causes[0].cause_id == "CPE-002"


def test_explicit_down_tunnel_critical(analyzer: OverlayAnalyzer) -> None:
    cfg = CpeConfiguration(
        hostname="cpe",
        vpn_tunnels=[VpnTunnelInfo(remote_ip="1.1.1.1", state="down")],
    )
    causes = analyzer.check_overlay_status(cfg)
    assert any(c.cause_id == "CPE-002" for c in causes)
