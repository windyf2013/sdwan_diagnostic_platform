"""GUI 报告交付统一逻辑单元测试。"""

from pathlib import Path

from sdwan_desktop.interface.gui.report_flow import (
    is_html_report,
    is_json_report,
)


def test_report_suffix_detection(tmp_path: Path) -> None:
    html = tmp_path / "r.html"
    html.write_text("<html></html>", encoding="utf-8")
    jsonf = tmp_path / "r.json"
    jsonf.write_text("{}", encoding="utf-8")
    assert is_html_report(html)
    assert not is_json_report(html)
    assert is_json_report(jsonf)
