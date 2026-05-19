"""GUI flow_run_params：argv 与 pydantic 边界。"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from sdwan_desktop.interface.gui.flow_run_params import (
    DEEP_DIVE_DEFAULT_BIZ_TARGETS,
    BusinessDiagnoseGuiRunParams,
    DeepDiveGuiRunParams,
    _resolve_credentials_path,
)


def test_deep_dive_to_argv_minimal() -> None:
    p = DeepDiveGuiRunParams(
        cpe_host="10.0.0.1",
        username="admin",
        output_path="/tmp/out.html",
    )
    argv = p.to_argv()
    assert argv[0] == "deep-dive"
    assert "--cpe-host" in argv and "10.0.0.1" in argv
    assert "-u" in argv and "admin" in argv
    assert "-p" in argv and "23" in argv
    # 默认应注入 3 个业务目标做链路分流（DNS(A)+TCP+traceroute），不做 DNS 系统对照
    assert argv.count("-b") == len(DEEP_DIVE_DEFAULT_BIZ_TARGETS) == 3
    for tgt in DEEP_DIVE_DEFAULT_BIZ_TARGETS:
        assert tgt in argv
    assert "--biz-dns-server" not in argv
    assert "--no-traceroute" not in argv


def test_deep_dive_explicit_biz_targets_override_defaults() -> None:
    p = DeepDiveGuiRunParams(
        cpe_host="10.0.0.1",
        username="admin",
        output_path="/tmp/out.html",
        biz_targets=("example.com:8443",),
    )
    argv = p.to_argv()
    assert argv.count("-b") == 1
    assert "example.com:8443" in argv
    for tgt in DEEP_DIVE_DEFAULT_BIZ_TARGETS:
        assert tgt not in argv


def test_business_diagnose_cpe_requires_user() -> None:
    with pytest.raises(ValueError, match="用户名"):
        BusinessDiagnoseGuiRunParams(
            biz_targets=("www.example.com:443",),
            output_path="/tmp/o.html",
            cpe_host="10.0.0.1",
            username=None,
        ).to_argv()


def test_business_diagnose_json_format() -> None:
    p = BusinessDiagnoseGuiRunParams(
        biz_targets=("a.example:443",),
        output_path="/tmp/o.json",
        output_format="json",
    )
    assert "-F" in p.to_argv() and "json" in p.to_argv()


def test_deep_dive_validation_empty_host() -> None:
    with pytest.raises(ValidationError):
        DeepDiveGuiRunParams(cpe_host="", username="u", output_path="/x.html")


def test_resolve_credentials_path_relative_uses_install_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CWD 下无该相对路径时，应回退到 resolve_resource_path（安装目录）。"""
    monkeypatch.chdir(tmp_path)
    install_cred = tmp_path / "install" / "cpe_credentials.yaml"
    install_cred.parent.mkdir(parents=True)
    install_cred.write_text("devices: {}\n", encoding="utf-8")

    def _fake_resolve(*parts: str) -> Path:
        assert parts == ("configs", "cpe_credentials.yaml")
        return install_cred

    monkeypatch.setattr(
        "sdwan_desktop.interface.gui.flow_run_params.resolve_resource_path",
        _fake_resolve,
    )
    resolved = _resolve_credentials_path("configs/cpe_credentials.yaml", kind="device")
    assert resolved == str(install_cred.resolve())


def test_deep_dive_argv_credentials_absolute_when_relative_missing_on_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    install_cred = tmp_path / "install" / "cpe_credentials.yaml"
    install_cred.parent.mkdir(parents=True)
    install_cred.write_text("devices: {}\n", encoding="utf-8")

    monkeypatch.setattr(
        "sdwan_desktop.interface.gui.flow_run_params.resolve_resource_path",
        lambda *parts: install_cred if parts == ("configs", "cpe_credentials.yaml") else None,
    )
    p = DeepDiveGuiRunParams(
        cpe_host="10.0.0.1",
        username="admin",
        output_path=str(tmp_path / "out.html"),
        credentials_file="configs/cpe_credentials.yaml",
    )
    argv = p.to_argv()
    assert "--credentials-file" in argv
    idx = argv.index("--credentials-file")
    assert Path(argv[idx + 1]).is_file()
