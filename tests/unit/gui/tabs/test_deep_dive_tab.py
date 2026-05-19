import pytest
from PySide6.QtWidgets import QLineEdit

from sdwan_desktop.interface.gui.tabs.deep_dive_tab import DeepDiveTab


def test_deep_dive_tab_creation(qapp):
    tab = DeepDiveTab()
    assert tab is not None
    assert tab.host_input is not None
    assert tab.password_input.echoMode() == QLineEdit.EchoMode.Password
    assert tab.port_spin.value() == 23


def test_deep_dive_build_params(qapp, tmp_path):
    from sdwan_desktop.interface.gui.flow_run_params import DEEP_DIVE_DEFAULT_BIZ_TARGETS

    tab = DeepDiveTab()
    tab.host_input.setText("10.10.25.1")
    tab.username_input.setText("admin")
    out = tmp_path / "r.html"
    params = tab._build_params(out)
    argv = params.to_argv()
    assert argv[0] == "deep-dive"
    assert "10.10.25.1" in argv
    # GUI 默认与 CLI 一致：注入 baidu/youtube/tiktok 三业务目标做链路分流
    assert argv.count("-b") == len(DEEP_DIVE_DEFAULT_BIZ_TARGETS) == 3
    for tgt in DEEP_DIVE_DEFAULT_BIZ_TARGETS:
        assert tgt in argv


def test_deep_dive_worker_signals(qapp):
    from sdwan_desktop.interface.gui.deep_dive_worker import DeepDiveWorker
    from sdwan_desktop.interface.gui.flow_run_params import DeepDiveGuiRunParams

    params = DeepDiveGuiRunParams(
        cpe_host="10.0.0.1",
        username="admin",
        output_path="x.html",
        password="secret",
    )
    worker = DeepDiveWorker(params, __import__("pathlib").Path("x.html"))
    assert hasattr(worker, "finished_ok")
    assert hasattr(worker, "cancel")
    assert hasattr(worker, "progress_updated")


def test_preview_button_initial_state(qapp):
    tab = DeepDiveTab()
    assert not tab.preview_btn.isEnabled()
