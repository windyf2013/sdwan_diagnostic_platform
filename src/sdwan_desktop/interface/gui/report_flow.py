"""GUI 诊断报告生成完成后的统一交付：保存、预览、打开位置。"""

from __future__ import annotations

import logging
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QPushButton, QWidget

if TYPE_CHECKING:
    from sdwan_desktop.interface.gui.main_window import MainWindow

logger = logging.getLogger(__name__)


@dataclass
class GuiReportActions:
    """各诊断页共用的报告操作按钮（可选挂载）。"""

    preview: Optional[QPushButton] = None
    open_folder: Optional[QPushButton] = None
    save_as: Optional[QPushButton] = None


def is_html_report(path: Path) -> bool:
    return path.suffix.lower() == ".html"


def is_json_report(path: Path) -> bool:
    return path.suffix.lower() == ".json"


def open_html_externally(path: Path) -> None:
    """核心版无内嵌预览时，用系统默认浏览器打开 HTML。"""
    uri = path.resolve().as_uri()
    if not webbrowser.open(uri):
        from sdwan_desktop.core.subprocess_platform import reveal_path_in_file_manager

        reveal_path_in_file_manager(path)


def prompt_save_report(path: Path, parent: Optional[QWidget]) -> Path:
    """弹出另存为；用户取消则返回原临时路径。"""
    if is_html_report(path):
        filt = "HTML (*.html);;All (*)"
        default_name = path.name if path.name.endswith(".html") else "report.html"
    elif is_json_report(path):
        filt = "JSON (*.json);;All (*)"
        default_name = path.name if path.name.endswith(".json") else "report.json"
    else:
        filt = "All (*)"
        default_name = path.name

    dest, _ = QFileDialog.getSaveFileName(parent, "保存报告", default_name, filt)
    if not dest:
        return path
    target = Path(dest)
    target.write_bytes(path.read_bytes())
    return target


def wire_report_action_labels(
    main: Optional[MainWindow],
    actions: GuiReportActions,
) -> None:
    """按主窗口是否支持内嵌预览，统一按钮文案。"""
    embedded = bool(main and getattr(main, "supports_embedded_preview", False))
    if actions.preview is not None:
        actions.preview.setText(
            "在报告预览中打开" if embedded else "在系统浏览器中打开"
        )
    if actions.open_folder is not None:
        actions.open_folder.setText("打开报告所在文件夹")
    if actions.save_as is not None:
        actions.save_as.setText("另存报告")


def set_report_actions_enabled(
    actions: GuiReportActions,
    path: Optional[Path],
    *,
    main: Optional[MainWindow] = None,
) -> None:
    """根据是否已有报告路径，启用/禁用操作按钮。"""
    ok = path is not None and path.is_file()
    html = ok and is_html_report(path)  # type: ignore[arg-type]
    if actions.preview is not None:
        actions.preview.setEnabled(bool(html))
    if actions.open_folder is not None:
        actions.open_folder.setEnabled(ok)
    if actions.save_as is not None:
        actions.save_as.setEnabled(ok)


def preview_report(
    main: Optional[MainWindow],
    path: Path,
    *,
    parent: Optional[QWidget] = None,
    switch_tab: bool = True,
) -> None:
    """在 embedded 预览页或系统浏览器中打开报告。"""
    if not path.is_file():
        return
    if is_html_report(path) and main is not None:
        main.open_report_preview(path, switch_tab=switch_tab, offer_save=False)
    elif is_html_report(path):
        open_html_externally(path)
    else:
        prompt_save_report(path, parent)


def open_report_folder(path: Path) -> None:
    from sdwan_desktop.core.subprocess_platform import reveal_path_in_file_manager

    if path.is_file():
        reveal_path_in_file_manager(path)


def deliver_gui_report(
    main: Optional[MainWindow],
    path: Path,
    *,
    status_setter: Callable[[str], None],
    actions: GuiReportActions,
    parent: Optional[QWidget] = None,
    auto_open: bool = True,
    prompt_save_on_complete: bool = True,
    defer_auto_open: bool = False,
) -> Path:
    """诊断完成后的统一报告交付（与 CLI 同一份 HTML/JSON 文件）。

    Args:
        main: 主窗口；``None`` 时仅更新状态与按钮。
        path: 流程输出的报告路径（多为临时文件）。
        status_setter: 更新页内状态文案。
        actions: 预览/打开文件夹/另存按钮。
        parent: 对话框父组件。
        auto_open: HTML 完成后是否自动打开预览（或浏览器）。
        prompt_save_on_complete: 完成时是否先弹出「另存为」（三类流一致）。
        defer_auto_open: 为真时用 ``QTimer`` 延后打开预览，避免阻塞 worker 收尾。

    Returns:
        最终报告路径（用户另存后可能变化）。
    """
    if not path.is_file():
        status_setter(f"失败：报告文件不存在 {path}")
        set_report_actions_enabled(actions, None, main=main)
        return path

    final = path
    if prompt_save_on_complete:
        final = prompt_save_report(path, parent)

    wire_report_action_labels(main, actions)
    set_report_actions_enabled(actions, final, main=main)

    status_setter(f"完成。报告: {final}")

    if auto_open and is_html_report(final):

        def _open() -> None:
            if main is not None:
                main.open_report_preview(final, switch_tab=True, offer_save=False)
            else:
                open_html_externally(final)

        if defer_auto_open:
            QTimer.singleShot(0, _open)
        elif main is not None:
            main.open_report_preview(final, switch_tab=True, offer_save=False)
        else:
            open_html_externally(final)

    logger.info("GUI report delivered: %s", final)
    return final
