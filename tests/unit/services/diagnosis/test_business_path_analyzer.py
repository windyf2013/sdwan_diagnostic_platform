"""Unit tests for BusinessPathAnalyzer."""

from sdwan_desktop.services.diagnosis.business_path_analyzer import BusinessPathAnalyzer


def test_analyzer_dns_error_emits_biz_dns_001() -> None:
    rows = [
        {
            "domain": "bad.example",
            "port": 443,
            "dns": {"status": "error", "data": None, "error": "timeout"},
            "tcp": [],
        }
    ]
    causes = BusinessPathAnalyzer().analyze(rows)
    assert len(causes) == 1
    assert causes[0].cause_id == "BIZ-DNS-001"


def test_analyzer_tcp_all_closed_emits_biz_tcp_001() -> None:
    rows = [
        {
            "domain": "svc.example",
            "port": 443,
            "dns": {
                "status": "ok",
                "data": {"resolved_ips": ["203.0.113.1"]},
                "error": None,
            },
            "tcp": [
                {
                    "host": "203.0.113.1",
                    "port": 443,
                    "status": "ok",
                    "data": {"port_open": False},
                }
            ],
        }
    ]
    causes = BusinessPathAnalyzer().analyze(rows)
    assert len(causes) == 1
    assert causes[0].cause_id in {"BIZ-TCP-001", "BIZ-TCP-TIMEOUT-001", "BIZ-TCP-REFUSED-001"}


def test_analyzer_dns_split_emits_split_cause() -> None:
    rows = [
        {
            "domain": "split.example",
            "port": 443,
            "dns": {
                "status": "ok",
                "data": {"resolved_ips": ["198.51.100.10"]},
                "error": None,
            },
            "dns_comparison": {
                "split_v4": True,
                "system": {"status": "ok", "data": {"resolved_ips": ["198.51.100.99"]}},
                "custom": {"status": "ok", "data": {"resolved_ips": ["198.51.100.10"]}},
            },
            "tcp": [],
        }
    ]
    causes = BusinessPathAnalyzer().analyze(rows)
    assert any(c.cause_id == "BIZ-DNS-SPLIT-001" for c in causes)


def test_analyzer_tcp_timeout_appends_icmp_trace_hint() -> None:
    rows = [
        {
            "domain": "slow.example",
            "port": 443,
            "dns": {
                "status": "ok",
                "data": {"resolved_ips": ["203.0.113.9"]},
                "error": None,
            },
            "tcp": [
                {
                    "host": "203.0.113.9",
                    "port": 443,
                    "status": "error",
                    "error": "connection timeout",
                }
            ],
            "trace": [
                {
                    "host": "203.0.113.9",
                    "port": 443,
                    "status": "ok",
                    "data": {
                        "summary": {"target_reached": False, "total_hops": 3, "last_hop_ip": "10.2.2.2"},
                        "hops": [],
                    },
                }
            ],
        }
    ]
    causes = BusinessPathAnalyzer().analyze(rows)
    tcp_cause = next(c for c in causes if c.cause_id.startswith("BIZ-TCP"))
    assert "路径旁证" in tcp_cause.description
    assert "203.0.113.9" in tcp_cause.description


def test_analyzer_healthy_no_causes() -> None:
    rows = [
        {
            "domain": "ok.example",
            "port": 443,
            "dns": {
                "status": "ok",
                "data": {"resolved_ips": ["203.0.113.2"]},
                "error": None,
            },
            "tcp": [
                {
                    "host": "203.0.113.2",
                    "port": 443,
                    "status": "ok",
                    "data": {"port_open": True},
                }
            ],
        }
    ]
    assert BusinessPathAnalyzer().analyze(rows) == []
