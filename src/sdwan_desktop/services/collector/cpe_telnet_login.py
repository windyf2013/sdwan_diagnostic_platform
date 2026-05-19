"""Telnet 登录阶段回显解析与用户可读错误信息。"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

# (pattern, 中文说明)
_LOGIN_FAILURE_RULES: Tuple[Tuple[str, str], ...] = (
    (
        r"already have four users|maximum\s+(?:number\s+of\s+)?(?:sessions|users)|"
        r"too many\s+(?:telnet\s+)?(?:sessions|users)|user\s+(?:sessions?\s+)?full|"
        r"会话.*满|登录用户.*满",
        "设备 Telnet 会话数已满，请断开其他终端上的空闲登录后重试",
    ),
    (
        r"login incorrect|bad\s+username|bad\s+password|invalid\s+password|"
        r"password\s+(?:error|fail|failed)|authentication\s+fail|"
        r"access denied|登录失败|密码错误|用户名或密码",
        "用户名或密码错误，或设备拒绝本次登录",
    ),
    (
        r"account\s+(?:is\s+)?locked|user\s+locked|账号.*锁定",
        "账号已被锁定",
    ),
    (
        r"connection refused|no route to host|host unreachable|网络不可达",
        "无法到达设备（网络不通或地址错误）",
    ),
)


def redact_secrets(text: str, secrets: Sequence[Optional[str]]) -> str:
    """从回显中脱敏密码等敏感字段。"""
    out = text or ""
    for secret in secrets:
        if not secret:
            continue
        out = out.replace(secret, "******")
    return out


def normalize_transcript_excerpt(text: str, *, max_len: int = 280) -> str:
    """压缩 Telnet 回显为单行摘要（便于报告与进度条）。"""
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in cleaned.split("\n") if ln.strip()]
    if not lines:
        return ""
    excerpt = " | ".join(lines[-8:])
    if len(excerpt) > max_len:
        excerpt = excerpt[-max_len:]
    return excerpt


def diagnose_telnet_login_failure(transcript: str) -> Optional[str]:
    """根据设备回显推断登录失败原因；无法识别时返回 None。"""
    if not transcript:
        return None
    low = transcript.lower()
    for pattern, message in _LOGIN_FAILURE_RULES:
        if re.search(pattern, low, re.I):
            return message
    pwd_idx = low.rfind("password")
    user_idx = low.rfind("username")
    if pwd_idx >= 0 and user_idx > pwd_idx:
        return "登录未成功（设备再次要求输入用户名，可能被拒绝或会话已满）"
    return None


def format_telnet_eof_error(*, host: str, port: int, transcript: str, secrets: Sequence[Optional[str]]) -> str:
    """对端关闭连接时的说明。"""
    excerpt = normalize_transcript_excerpt(redact_secrets(transcript, secrets))
    msg = f"Telnet 连接已由对端关闭（EOF）: {host}:{port}"
    if excerpt:
        msg = f"{msg}；设备回显: {excerpt}"
    return msg


def build_telnet_login_error(
    *,
    stage: str,
    host: str,
    port: int,
    transcript: str,
    secrets: Sequence[Optional[str]],
    timed_out: bool = False,
) -> str:
    """构造面向用户的 Telnet 登录失败说明（不含明文密码）。"""
    redacted = redact_secrets(transcript, secrets)
    hint = diagnose_telnet_login_failure(redacted)
    excerpt = normalize_transcript_excerpt(redacted)

    parts: List[str] = [f"Telnet 登录失败（{stage}）: {host}:{port}"]
    if hint:
        parts.append(f"原因: {hint}")
    elif timed_out:
        parts.append("原因: 等待设备响应超时，未出现命令行提示符（# 或 >）")
    else:
        parts.append("原因: 设备未返回可识别的登录成功提示符")
    if excerpt:
        parts.append(f"设备回显: {excerpt}")
    return "；".join(parts)
