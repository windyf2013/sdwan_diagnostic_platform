"""业务 RCA 验收矩阵（轻量自动化，对齐方案 §4 场景）。"""

from sdwan_desktop.core.types.business_rca import ObservationContext, ProbeBundle
from sdwan_desktop.services.diagnosis.business_path_analyzer import BusinessPathAnalyzer
from sdwan_desktop.services.diagnosis.business_rca_engine import BusinessRCAEngine


def _matrix_tcp_rst_style() -> list:
    """DNS 正常、TCP 端口未打开（类 RST/拒绝语义由 port_open=False 代表）。"""
    return [
        {
            "domain": "svc.example",
            "port": 443,
            "dns": {"status": "ok", "data": {"resolved_ips": ["198.51.100.1"]}, "error": None},
            "tcp": [
                {
                    "host": "198.51.100.1",
                    "port": 443,
                    "status": "ok",
                    "data": {"port_open": False},
                }
            ],
        }
    ]


def test_matrix_dns_ok_tcp_closed_prefers_tcp_cause_not_dns() -> None:
    """场景：DNS 正常、TCP 失败 → 应出现 BIZ-TCP-*，不应出现 BIZ-DNS-001。"""
    rows = _matrix_tcp_rst_style()
    causes = BusinessPathAnalyzer().analyze(rows)
    ids = {c.cause_id for c in causes}
    assert any(cid.startswith("BIZ-TCP") for cid in ids)
    assert "BIZ-DNS-001" not in ids


def test_matrix_dns_split_flag() -> None:
    """场景：系统与显式 DNS IPv4 集合不一致 → BIZ-DNS-SPLIT-001。"""
    rows = [
        {
            "domain": "d.example",
            "port": 443,
            "dns": {"status": "ok", "data": {"resolved_ips": ["1.1.1.1"]}, "error": None},
            "dns_comparison": {
                "split_v4": True,
                "system": {"status": "ok", "data": {"resolved_ips": ["8.8.8.8"]}},
                "custom": {"status": "ok", "data": {"resolved_ips": ["1.1.1.1"]}},
            },
            "tcp": [],
        }
    ]
    assert any(c.cause_id == "BIZ-DNS-SPLIT-001" for c in BusinessPathAnalyzer().analyze(rows))


def test_matrix_no_cpe_evidence_tcp_gets_boundary_note() -> None:
    """无 CPE 证据时 BIZ-TCP 应带 needs_cpe 提示（经 BusinessRCAEngine）。"""
    obs = ObservationContext(trace_id="qa-1", pc=None, cpe_evidence_available=False)
    bundle = ProbeBundle(trace_id="qa-1", business_probes=_matrix_tcp_rst_style())
    causes = BusinessRCAEngine().analyze(obs, bundle)
    tcp = next(c for c in causes if c.cause_id.startswith("BIZ-TCP"))
    assert "本机出站段" in tcp.description or "CPE" in tcp.description
