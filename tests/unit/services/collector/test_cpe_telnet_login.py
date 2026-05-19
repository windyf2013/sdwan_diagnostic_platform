"""Telnet 登录失败信息解析。"""

from sdwan_desktop.services.collector.cpe_telnet_login import (
    build_telnet_login_error,
    diagnose_telnet_login_failure,
    normalize_transcript_excerpt,
    redact_secrets,
)


def test_diagnose_four_users() -> None:
    raw = "Password:\r\nDevice already have four users\r\nUsername: "
    assert diagnose_telnet_login_failure(raw) is not None
    assert "会话" in diagnose_telnet_login_failure(raw) or "满" in diagnose_telnet_login_failure(raw)


def test_diagnose_login_incorrect() -> None:
    assert diagnose_telnet_login_failure("Login incorrect") is not None


def test_redact_password() -> None:
    assert "secret" not in redact_secrets("pass secret end", ["secret"])


def test_build_error_includes_excerpt() -> None:
    msg = build_telnet_login_error(
        stage="提交密码后",
        host="10.0.0.1",
        port=23,
        transcript="Device already have four users",
        secrets=["x"],
        timed_out=False,
    )
    assert "10.0.0.1:23" in msg
    assert "原因:" in msg
    assert "four users" in msg or "会话" in msg


def test_normalize_excerpt_collapses_lines() -> None:
    raw = "line1\r\n\r\nline2\r\n"
    out = normalize_transcript_excerpt(raw)
    assert "line1" in out and "line2" in out
