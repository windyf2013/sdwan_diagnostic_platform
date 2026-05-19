"""Raisecom MSG5200B 解析器与 5200A 互斥探测单元测试。"""

from pathlib import Path

import pytest

from sdwan_desktop.services.parser.vendor.raisecom_msg5200 import (
    RaisecomMsg5200Parser,
    is_raisecom_msg5200a_version_output,
    is_raisecom_msg5200b_version_output,
)
from sdwan_desktop.services.parser.vendor.raisecom_msg5200b import RaisecomMsg5200BParser


def _read_template_tail(name: str, max_chars: int = 4000) -> str:
    root = Path(__file__).resolve().parents[4]
    path = root / "templates" / name
    text = path.read_text(encoding="utf-8", errors="ignore")
    return text[:max_chars]


@pytest.fixture
def parser_a() -> RaisecomMsg5200Parser:
    return RaisecomMsg5200Parser()


@pytest.fixture
def parser_b() -> RaisecomMsg5200BParser:
    return RaisecomMsg5200BParser()


def test_detect_5200b_from_template(parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser) -> None:
    sample = _read_template_tail("whole_config_5200b.txt")
    assert parser_b.detect_vendor(sample) is True
    assert parser_a.detect_vendor(sample) is False


def test_detect_5200a_from_template(parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser) -> None:
    sample = _read_template_tail("whole_config_5200a.txt")
    assert parser_b.detect_vendor(sample) is False
    assert parser_a.detect_vendor(sample) is True


def test_detect_5200b_rcios_433_or_pv_b00(parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser) -> None:
    """5200B：RCIOS 4.33.xxx 或 PV B.00（与型号字符串无关）。"""
    by_rcios = "RCIOS version   : 4.33.152.20260313\nhost#"
    assert is_raisecom_msg5200b_version_output(by_rcios) is True
    assert is_raisecom_msg5200a_version_output(by_rcios) is False
    assert parser_b.detect_vendor(by_rcios) is True
    assert parser_a.detect_vendor(by_rcios) is False

    by_pv = "Product Name    : MSG5200-XGE-8E\nPV              : B.00\nhost#"
    assert is_raisecom_msg5200b_version_output(by_pv) is True
    assert parser_b.detect_vendor(by_pv) is True
    assert parser_a.detect_vendor(by_pv) is False


def test_detect_msg5200_product_version_433_classifies_b(
    parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser,
) -> None:
    """``Product Version`` 值含 433 时判为 5200B（不依赖 Software Version）。"""
    sample = (
        "Copyright (c) Raisecom\n"
        "Product Name    : MSG5200-XGE-8E\n"
        "Product series  : P410_433_2511\n"
        "Software Version: P410_XXX_2511\n"
        "Product Version : P410_433_2511\n"
        "host#"
    )
    assert is_raisecom_msg5200b_version_output(sample) is True
    assert is_raisecom_msg5200a_version_output(sample) is False
    assert parser_b.detect_vendor(sample) is True
    assert parser_a.detect_vendor(sample) is False


def test_detect_msg5200_product_series_433_without_rcios_classifies_b(
    parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser,
) -> None:
    """部分固件仅输出 ``Product series`` 含 433（无 RCIOS 行）时仍须判为 5200B，避免误走 diagnose 入口。"""
    sample = (
        "Copyright (c) Raisecom\n"
        "PN              : MSG5200-XGE-8E-G5\n"
        "Product series  : P410_433_2511\n"
        "host#"
    )
    assert is_raisecom_msg5200b_version_output(sample) is True
    assert is_raisecom_msg5200a_version_output(sample) is False
    assert parser_b.detect_vendor(sample) is True
    assert parser_a.detect_vendor(sample) is False


def test_detect_msg5200_product_version_423_classifies_a(
    parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser,
) -> None:
    """``Product Version`` 值含 423 时判为 5200A，与 5200B 互斥。"""
    sample = (
        "Copyright (c) Raisecom\n"
        "Product Name    : MSG5200-XGE-8E\n"
        "Software Version: P410_999_2511\n"
        "Product Version : P410_423_2511\n"
        "host#"
    )
    assert is_raisecom_msg5200a_version_output(sample) is True
    assert is_raisecom_msg5200b_version_output(sample) is False
    assert parser_b.detect_vendor(sample) is False
    assert parser_a.detect_vendor(sample) is True


def test_detect_msg5200_product_series_423_without_rcios_not_explicit_a(
    parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser,
) -> None:
    """5200A 的 ``Product series`` 不稳定：仅 series 含 423 不作为显式 A 指纹，由 A 解析器在排除 B 后兜底。"""
    sample = (
        "Copyright (c) Raisecom\n"
        "PN              : MSG5200-GEC-8E-G4\n"
        "Product series  : P410_423_2511\n"
        "host#"
    )
    assert is_raisecom_msg5200a_version_output(sample) is False
    assert is_raisecom_msg5200b_version_output(sample) is False
    assert parser_b.detect_vendor(sample) is False
    assert parser_a.detect_vendor(sample) is True


def test_detect_msg5200_product_version_b00_classifies_b(
    parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser,
) -> None:
    """5200B：``Product Version`` 固定为 ``B.00`` 时可判 B（无需 ``Software Version``）。"""
    sample = (
        "Copyright (c) Raisecom\n"
        "msg5200\n"
        "Product Version : B.00\n"
        "host#"
    )
    assert is_raisecom_msg5200b_version_output(sample) is True
    assert is_raisecom_msg5200a_version_output(sample) is False
    assert parser_b.detect_vendor(sample) is True
    assert parser_a.detect_vendor(sample) is False


def test_detect_msg5200_product_version_a00_classifies_a(
    parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser,
) -> None:
    """5200A：``Product Version`` 固定为 ``A.00`` 时可判为显式 A。"""
    sample = (
        "Copyright (c) Raisecom\n"
        "msg5200\n"
        "Product Version : A.00\n"
        "host#"
    )
    assert is_raisecom_msg5200a_version_output(sample) is True
    assert is_raisecom_msg5200b_version_output(sample) is False
    assert parser_b.detect_vendor(sample) is False
    assert parser_a.detect_vendor(sample) is True


def test_detect_msg5200_software_version_only_433_does_not_classify_b(
    parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser,
) -> None:
    """Software Version 不可靠：仅有 Software Version 含 433 而无 Product Version 指纹时不判 B。"""
    sample = (
        "Copyright (c) Raisecom\n"
        "Product Name    : MSG5200-XGE-8E\n"
        "Software Version: P410_433_2511\n"
        "host#"
    )
    assert is_raisecom_msg5200b_version_output(sample) is False
    assert parser_b.detect_vendor(sample) is False
    assert parser_a.detect_vendor(sample) is True


def test_detect_msg5200_without_b_fingerprint_defaults_to_a(
    parser_a: RaisecomMsg5200Parser, parser_b: RaisecomMsg5200BParser,
) -> None:
    """无 RCIOS/PV/Product Version 423 与 433 等 B 指纹时，由 5200A 解析器兜底。"""
    sample = (
        "Copyright (c) Raisecom\n"
        "Product Name    : MSG5200-XGE-8E\n"
        "Product series  : P410_XXX_2511\n"
        "Software Version: P410_XXX_2511\n"
        "host#"
    )
    assert is_raisecom_msg5200b_version_output(sample) is False
    assert parser_b.detect_vendor(sample) is False
    assert parser_a.detect_vendor(sample) is True


def test_parse_all_sets_vendor_b() -> None:
    raw = {
        "show version": "Product Name    : MSG5200-XGE-8E\nRCIOS version   : 4.33.1.20260313\nhost#",
        "show running-config": "!config\nhostname lab5200b\n!\n!end\nhost#",
        "show ip route": "",
    }
    cfg = RaisecomMsg5200BParser().parse_all(raw)
    assert cfg.vendor == "raisecom_msg5200b"


def test_detect_hostname_prefers_running_config_over_enable_cmd(
    parser_a: RaisecomMsg5200Parser,
) -> None:
    assert (
        parser_a._detect_hostname(
            "!\nhostname from-rcios\n",
            hostname_command_out="from-enable\n",
        )
        == "from-rcios"
    )


def test_detect_hostname_enable_command_fallback(parser_a: RaisecomMsg5200Parser) -> None:
    assert parser_a._detect_hostname("", hostname_command_out="kernel-only\n") == "kernel-only"


def test_parse_vpn_tunnels_tunnel_name_with_underscore(parser_b: RaisecomMsg5200BParser) -> None:
    """running-config 中 tunnel1_5 等形式须完整匹配（旧正则 tunnel\\d+ 会在 tunnel1 处截断导致匹配失败）。"""
    rc = """
tunnel tunnel1_5
type vxlan source-id raisecom-soft2 interval 10
 peer 5.0.1.1
exit
"""
    tunnels = parser_b.parse_vpn_tunnels(rc)
    assert len(tunnels) == 1
    assert tunnels[0].local_color == "tunnel1_5"
    assert tunnels[0].remote_ip == "5.0.1.1"
    assert tunnels[0].type == "vxlan"
    assert tunnels[0].raw_block


def test_parse_all_hostname_from_enable_command_when_config_missing(
    parser_a: RaisecomMsg5200Parser,
) -> None:
    raw = {
        "show version": "RCIOS version   : 4.23.1.20250805\nPN : MSG5200\nhost#",
        "show running-config": "!config\n! no hostname line\n",
        "show ip route": "",
        "hostname": "from-enable\n",
    }
    cfg = parser_a.parse_all(raw)
    assert cfg.hostname == "from-enable"
