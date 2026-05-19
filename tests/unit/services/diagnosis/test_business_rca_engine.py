"""BusinessRCAEngine 与观测契约单元测试。"""

from sdwan_desktop.core.types.business_rca import ObservationContext, PCObservationSummary, ProbeBundle
from sdwan_desktop.services.collector.base import CollectorResult
from sdwan_desktop.services.diagnosis.business_rca_engine import (
    BusinessRCAEngine,
    build_observation_for_analysis,
    build_probe_bundle_from_targeted,
)
from sdwan_desktop.services.topology.topology import NetworkTopology, Node, NodeType


def test_pc_observation_empty_dict_returns_none() -> None:
    assert PCObservationSummary.from_snapshot_like({}, "t1") is None


def test_rca_engine_adds_confidence_when_no_pc() -> None:
    obs = ObservationContext(trace_id="t-x", pc=None, cpe_evidence_available=False)
    bundle = ProbeBundle(
        trace_id="t-x",
        business_probes=[
            {
                "domain": "a.example",
                "port": 443,
                "dns": {"status": "ok", "data": {"resolved_ips": ["203.0.113.1"]}, "error": None},
                "tcp": [
                    {
                        "host": "203.0.113.1",
                        "port": 443,
                        "status": "ok",
                        "data": {"port_open": False},
                    }
                ],
            }
        ],
    )
    causes = BusinessRCAEngine().analyze(obs, bundle)
    ids = [c.cause_id for c in causes]
    assert "BIZ-CONF-001" in ids
    assert any(cid.startswith("BIZ-TCP") for cid in ids)


def test_rca_hypotheses_include_icmp_trace_when_trace_ok() -> None:
    obs = ObservationContext(trace_id="t-h", pc=None, cpe_evidence_available=False)
    bundle = ProbeBundle(
        trace_id="t-h",
        business_probes=[
            {
                "domain": "p.example",
                "port": 443,
                "dns": {"status": "ok", "data": {"resolved_ips": ["1.1.1.1"]}, "error": None},
                "tcp": [{"host": "1.1.1.1", "port": 443, "status": "ok", "data": {"port_open": True}}],
                "trace": [
                    {
                        "host": "1.1.1.1",
                        "port": 443,
                        "status": "ok",
                        "data": {"summary": {"target_reached": True, "total_hops": 5}, "hops": []},
                    }
                ],
            }
        ],
    )
    hyps = BusinessRCAEngine().hypotheses(obs, bundle)
    assert any(h.hypothesis_id == "H-ICMP-TRACE" for h in hyps)


def test_build_probe_bundle_respects_status() -> None:
    assert build_probe_bundle_from_targeted("t", {"status": "skipped", "data": {"business_probes": [{}]}}) is None
    b = build_probe_bundle_from_targeted(
        "t",
        {"status": "ok", "data": {"business_probes": [{"domain": "x", "port": 80, "dns": {}, "tcp": []}]}},
    )
    assert b is not None
    assert len(b.business_probes) == 1


def test_build_observation_marks_cpe_available() -> None:
    topo = NetworkTopology()
    topo.add_node(Node(id="cpe-1", name="C", node_type=NodeType.CPE, ip_address="10.0.0.1"))
    topo.cpe_node_id = "cpe-1"
    from sdwan_desktop.core.types.cpe_config import CpeConfiguration

    cfg = CpeConfiguration(vendor="cisco")
    res = CollectorResult(success=True, data={"cpe_configuration": cfg})
    obs = build_observation_for_analysis(
        "tid",
        None,
        {"primary_ip": "192.168.1.2", "hostname": "pc1"},
        res,
        topo,
    )
    assert obs.cpe_evidence_available is True
    assert obs.pc is not None
    assert obs.pc.primary_ip == "192.168.1.2"
