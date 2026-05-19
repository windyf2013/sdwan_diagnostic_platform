"""三条功能流 GUI 入口参数（pydantic 校验后拼装 agentctl argv）。"""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sdwan_desktop.core.app_paths import resolve_resource_path
from sdwan_desktop.flow.definitions.deep_dive import DEEP_DIVE_DEFAULT_BIZ_TARGETS

_CREDENTIALS_REL: dict[str, tuple[str, ...]] = {
    "device": ("configs", "cpe_credentials.yaml"),
    "view": ("configs", "cpe_view_credentials.yaml"),
}


def _resolve_existing_path(path: Optional[str]) -> Optional[str]:
    """子进程工作目录可能与 GUI 不同，已存在文件尽量传绝对路径。"""
    if not path or not str(path).strip():
        return None
    p = Path(path).expanduser()
    if p.is_file():
        return str(p.resolve())
    return str(p)


def _resolve_credentials_path(
    path: Optional[str], *, kind: Literal["device", "view"]
) -> Optional[str]:
    """解析 CPE 凭证 YAML 为绝对路径。

    GUI 常展示 ``configs/cpe_credentials.yaml``（相对当前工作目录）。子进程 CWD
    若与 GUI 不一致，会把该相对路径原样传给 CLI；Click 认为用户已指定路径，便不再
    走 ``default_cpe_credentials_path()``，导致 YAML 内密码读不到、Telnet 失败。
    仅当文件真实存在时才写入 ``--credentials-file``；否则省略，由 CLI 按安装目录解析。
    """
    rel_parts = _CREDENTIALS_REL[kind]
    if path and str(path).strip():
        candidate = Path(path).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        installed = resolve_resource_path(*rel_parts)
        if installed is not None and installed.is_file():
            return str(installed.resolve())
        return None
    installed = resolve_resource_path(*rel_parts)
    if installed is not None and installed.is_file():
        return str(installed.resolve())
    return None


def _append_cpe_auth_argv(
    cmd: List[str],
    *,
    password: Optional[str],
    key_file: Optional[str],
    credentials_file: Optional[str],
    view_credentials_file: Optional[str],
    protocol: str,
) -> None:
    if password:
        cmd.extend(["--password", password])
    if key_file:
        cmd.extend(["--key-file", key_file])
    cmd.extend(["--protocol", protocol])
    cred = _resolve_credentials_path(credentials_file, kind="device")
    if cred:
        cmd.extend(["--credentials-file", cred])
    view_cred = _resolve_credentials_path(view_credentials_file, kind="view")
    if view_cred:
        cmd.extend(["--view-credentials-file", view_cred])


class DeepDiveGuiRunParams(BaseModel):
    """深度诊断 GUI → ``deep-dive`` CLI 参数。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cpe_host: str = Field(min_length=1)
    username: str = Field(min_length=1)
    cpe_port: int = Field(default=23, ge=1, le=65535)
    password: Optional[str] = None
    key_file: Optional[str] = None
    protocol: Literal["telnet", "ssh"] = "telnet"
    output_path: str = Field(min_length=1)
    credentials_file: Optional[str] = None
    view_credentials_file: Optional[str] = None
    biz_targets: Tuple[str, ...] = DEEP_DIVE_DEFAULT_BIZ_TARGETS
    biz_dns_server: Optional[str] = None
    no_traceroute: bool = False
    verbose: bool = False

    @field_validator("biz_targets", mode="before")
    @classmethod
    def _coerce_targets(cls, v: object) -> Tuple[str, ...]:
        if v is None:
            return DEEP_DIVE_DEFAULT_BIZ_TARGETS
        if isinstance(v, str):
            lines = [ln.strip() for ln in v.splitlines() if ln.strip()]
            return tuple(lines) if lines else DEEP_DIVE_DEFAULT_BIZ_TARGETS
        coerced = tuple(str(x).strip() for x in v if str(x).strip())
        return coerced if coerced else DEEP_DIVE_DEFAULT_BIZ_TARGETS

    def to_argv(self) -> List[str]:
        cmd: List[str] = [
            "deep-dive",
            "--cpe-host",
            self.cpe_host,
            "-u",
            self.username,
            "-p",
            str(self.cpe_port),
            "-o",
            _resolve_existing_path(self.output_path) or self.output_path,
        ]
        _append_cpe_auth_argv(
            cmd,
            password=self.password,
            key_file=_resolve_existing_path(self.key_file),
            credentials_file=self.credentials_file,
            view_credentials_file=self.view_credentials_file,
            protocol=self.protocol,
        )
        for t in self.biz_targets:
            cmd.extend(["-b", t])
        if self.biz_dns_server:
            cmd.extend(["--biz-dns-server", self.biz_dns_server])
        if self.no_traceroute:
            cmd.append("--no-traceroute")
        if self.verbose:
            cmd.append("--verbose")
        return cmd


class BusinessDiagnoseGuiRunParams(BaseModel):
    """业务路径诊断 GUI → ``business-diagnose`` CLI 参数。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    biz_targets: Tuple[str, ...] = Field(min_length=1)
    output_path: str = Field(min_length=1)
    output_format: Literal["html", "json"] = "html"
    biz_dns_server: Optional[str] = None
    collect_pc: bool = True
    allow_probe_only: bool = False
    no_traceroute: bool = False
    cpe_host: Optional[str] = None
    cpe_port: int = Field(default=23, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    key_file: Optional[str] = None
    protocol: Literal["telnet", "ssh"] = "telnet"
    credentials_file: Optional[str] = None
    view_credentials_file: Optional[str] = None
    verbose: bool = False

    @field_validator("biz_targets", mode="before")
    @classmethod
    def _coerce_targets(cls, v: object) -> Tuple[str, ...]:
        if isinstance(v, str):
            lines = [ln.strip() for ln in v.splitlines() if ln.strip()]
            return tuple(lines)
        seq: Sequence[str] = v  # type: ignore[assignment]
        return tuple(str(x).strip() for x in seq if str(x).strip())

    def to_argv(self) -> List[str]:
        cmd: List[str] = [
            "business-diagnose",
            "-o",
            _resolve_existing_path(self.output_path) or self.output_path,
            "-F",
            self.output_format,
        ]
        for t in self.biz_targets:
            cmd.extend(["-b", t])
        if self.biz_dns_server:
            cmd.extend(["--biz-dns-server", self.biz_dns_server])
        if not self.collect_pc:
            cmd.append("--no-collect-pc")
        if self.allow_probe_only:
            cmd.append("--allow-probe-only")
        if self.no_traceroute:
            cmd.append("--no-traceroute")
        host = (self.cpe_host or "").strip()
        if host:
            user = (self.username or "").strip()
            if not user:
                raise ValueError("填写 CPE 地址时必须同时填写用户名")
            cmd.extend(["--cpe-host", host, "-p", str(self.cpe_port), "-u", user])
            _append_cpe_auth_argv(
                cmd,
                password=self.password,
                key_file=_resolve_existing_path(self.key_file),
                credentials_file=self.credentials_file,
                view_credentials_file=self.view_credentials_file,
                protocol=self.protocol,
            )
        if self.verbose:
            cmd.append("--verbose")
        return cmd
