"""business_diagnose_followup：探测失败门控。"""

from sdwan_desktop.services.diagnosis.business_diagnose_followup import (
    business_probe_requires_joint_diagnosis,
)
from sdwan_desktop.services.diagnosis.business_diagnosis import BusinessDiagnosisOutcome


def test_joint_not_required_when_all_ok() -> None:
    o = BusinessDiagnosisOutcome(
        status="ok",
        business_probes=[
            {
                "domain": "a.example",
                "port": 443,
                "dns": {"status": "ok", "data": {"resolved_ips": ["1.1.1.1"]}, "error": None},
                "tcp": [
                    {
                        "host": "1.1.1.1",
                        "port": 443,
                        "status": "ok",
                        "data": {"port_open": True},
                    }
                ],
            }
        ],
        aggregate_error=None,
    )
    assert business_probe_requires_joint_diagnosis(o) is False


def test_joint_not_required_when_traceroute_row_errors_but_tcp_ok() -> None:
    """仅 traceroute 失败：不要求联合（与 ``business_probe_requires_joint_diagnosis`` 口径一致）。"""
    o = BusinessDiagnosisOutcome(
        status="ok",
        business_probes=[
            {
                "domain": "a.example",
                "port": 443,
                "dns": {"status": "ok", "data": {"resolved_ips": ["1.1.1.1"]}, "error": None},
                "tcp": [
                    {
                        "host": "1.1.1.1",
                        "port": 443,
                        "status": "ok",
                        "data": {"port_open": True},
                    }
                ],
                "trace": [{"host": "1.1.1.1", "port": 443, "status": "error", "error": "tool failed"}],
            }
        ],
        aggregate_error=None,
    )
    assert business_probe_requires_joint_diagnosis(o) is False


def test_joint_required_on_tcp_error() -> None:
    o = BusinessDiagnosisOutcome(
        status="partial",
        business_probes=[
            {
                "domain": "a.example",
                "port": 443,
                "dns": {"status": "ok", "data": {"resolved_ips": ["1.1.1.1"]}, "error": None},
                "tcp": [{"host": "1.1.1.1", "port": 443, "status": "error", "error": "timeout"}],
            }
        ],
        aggregate_error=None,
    )
    assert business_probe_requires_joint_diagnosis(o) is True


def test_joint_required_on_port_closed() -> None:
    o = BusinessDiagnosisOutcome(
        status="ok",
        business_probes=[
            {
                "domain": "a.example",
                "port": 443,
                "dns": {"status": "ok", "data": {"resolved_ips": ["1.1.1.1"]}, "error": None},
                "tcp": [
                    {
                        "host": "1.1.1.1",
                        "port": 443,
                        "status": "ok",
                        "data": {"port_open": False},
                    }
                ],
            }
        ],
        aggregate_error=None,
    )
    assert business_probe_requires_joint_diagnosis(o) is True
