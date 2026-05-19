import pytest

from sdwan_desktop.interface.gui.tabs.quick_check_tab import QuickCheckTab, QuickCheckWorker
from sdwan_desktop.core.types.quick_check_run_config import QuickCheckRunConfig


def test_quick_check_tab_creation(qapp):
    tab = QuickCheckTab()
    assert tab is not None
    assert tab.start_btn is not None
    assert tab.result_table is not None


def test_quick_check_worker_signals(qapp):
    cfg = QuickCheckRunConfig(output_format="html", report_output=None)
    worker = QuickCheckWorker(cfg)
    assert hasattr(worker, "progress_updated")
    assert hasattr(worker, "diagnosis_completed")
    assert hasattr(worker, "cancel")


def test_preview_button_initial_state(qapp):
    tab = QuickCheckTab()
    assert not tab.preview_btn.isEnabled()
