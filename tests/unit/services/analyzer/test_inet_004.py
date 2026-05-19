"""INET-004 部分业务探针不可达规则测试"""

from sdwan_desktop.core.types.probe import ProbeResult, ProbeTarget
from sdwan_desktop.services.analyzer.rules.connectivity import (
    _evaluate_inet_002,
    _evaluate_inet_004,
    _build_inet_004_message,
)


def _probe(host: str, success: bool) -> ProbeResult:
    return ProbeResult(
        target=ProbeTarget(host=host, protocol="icmp"),
        success=success,
    )


class _Ctx:
    def __init__(self, domestic, international):
        self.domestic_target_results = domestic
        self.international_target_results = international


def test_inet_004_fires_when_one_international_fails():
    ctx = _Ctx(
        [_probe("www.baidu.com", True)],
        [_probe("www.youtube.com", True), _probe("www.tiktok.com", False)],
    )
    assert _evaluate_inet_004(ctx) is True
    assert "tiktok" in _build_inet_004_message(ctx)


def test_inet_004_not_when_all_international_fail():
    ctx = _Ctx(
        [_probe("www.baidu.com", True)],
        [_probe("www.youtube.com", False), _probe("www.tiktok.com", False)],
    )
    assert _evaluate_inet_004(ctx) is False
    assert _evaluate_inet_002(ctx) is True


def test_inet_004_not_when_all_ok():
    ctx = _Ctx(
        [_probe("www.baidu.com", True)],
        [_probe("www.youtube.com", True), _probe("www.tiktok.com", True)],
    )
    assert _evaluate_inet_004(ctx) is False
