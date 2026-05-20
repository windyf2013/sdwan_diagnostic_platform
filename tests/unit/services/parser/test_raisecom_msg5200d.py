"""Raisecom MSG5200D 解析器与 5200B 互斥探测单元测试。"""

from pathlib import Path

import pytest

from sdwan_desktop.services.parser.vendor.raisecom_msg5200 import (
    RaisecomMsg5200Parser,
    is_raisecom_msg5200b_version_output,
    is_raisecom_msg5200d_version_output,
)
from sdwan_desktop.services.parser.vendor.raisecom_msg5200b import RaisecomMsg5200BParser
from sdwan_desktop.services.parser.vendor.raisecom_msg5200d import RaisecomMsg5200DParser


def _read_template(name: str) -> str:
    root = Path(__file__).resolve().parents[4]
    return (root / "templates" / name).read_text(encoding="utf-8", errors="ignore")


@pytest.fixture
def parser_a() -> RaisecomMsg5200Parser:
    return RaisecomMsg5200Parser()


@pytest.fixture
def parser_b() -> RaisecomMsg5200BParser:
    return RaisecomMsg5200BParser()


@pytest.fixture
def parser_d() -> RaisecomMsg5200DParser:
    return RaisecomMsg5200DParser()


def test_detect_5200d_from_feature_template(
    parser_b: RaisecomMsg5200BParser,
    parser_d: RaisecomMsg5200DParser,
    parser_a: RaisecomMsg5200Parser,
) -> None:
    sample = _read_template("feature_config_5200d.txt")
    assert is_raisecom_msg5200d_version_output(sample) is True
    assert is_raisecom_msg5200b_version_output(sample) is False
    assert parser_d.detect_vendor(sample) is True
    assert parser_b.detect_vendor(sample) is False
    assert parser_a.detect_vendor(sample) is False


def test_detect_5200d_pv_d00(
    parser_b: RaisecomMsg5200BParser,
    parser_d: RaisecomMsg5200DParser,
) -> None:
    sample = (
        "Product series  : P410_433\n"
        "RCIOS version   : 4.33.51.20260509\n"
        "PN              : MSG5200-2GEC-4E-X4\n"
        "PV              : D.00\n"
        "host#"
    )
    assert is_raisecom_msg5200d_version_output(sample) is True
    assert is_raisecom_msg5200b_version_output(sample) is False
    assert parser_d.detect_vendor(sample) is True
    assert parser_b.detect_vendor(sample) is False


def test_detect_5200b_still_excludes_d_series_433(
    parser_b: RaisecomMsg5200BParser,
    parser_d: RaisecomMsg5200DParser,
) -> None:
    """5200B 模板仍判 B；同 series 433 但 PV D.00 须归 D。"""
    b_sample = _read_template("whole_config_5200b.txt")[:4000]
    assert parser_b.detect_vendor(b_sample) is True
    assert parser_d.detect_vendor(b_sample) is False


def test_parse_all_sets_vendor_d() -> None:
    raw = {
        "show version": (
            "PN              : MSG5200-2GEC-4E-X4\n"
            "Product series  : P410_433\n"
            "RCIOS version   : 4.33.51.20260509\n"
            "PV              : D.00\n"
            "host#"
        ),
        "show running-config": "!config\nhostname lab5200d\n!\n!end\nhost#",
        "show ip route": "",
    }
    cfg = RaisecomMsg5200DParser().parse_all(raw)
    assert cfg.vendor == "raisecom_msg5200d"
