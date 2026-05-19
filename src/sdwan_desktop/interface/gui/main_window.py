import os
import sys

# PyInstaller 打包后的模块查找
if getattr(sys, "frozen", False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

if application_path not in sys.path:
    sys.path.insert(0, application_path)

for path in (
    os.path.join(application_path, "src"),
    os.path.join(os.path.dirname(application_path), "src"),
    application_path,
):
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

from sdwan_desktop.core.app_paths import configure_playwright_browsers_path

configure_playwright_browsers_path()

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from sdwan_desktop.interface.gui.app_branding import (
    GUI_CORE_DISPLAY_SUFFIX,
    GUI_DISPLAY_NAME,
)
from sdwan_desktop.interface.gui.app_icon import apply_app_icon, configure_platform_icon
from sdwan_desktop.interface.gui.deferred_tab import DeferredTabHost
from sdwan_desktop.interface.gui.report_flow import open_html_externally
from sdwan_desktop.interface.gui.styles.theme import ThemeManager

PROFILE_FULL = "full"
PROFILE_CORE = "core"


class MainWindow(QMainWindow):
    def __init__(self, profile: str = PROFILE_FULL) -> None:
        super().__init__()
        self._profile = profile if profile in (PROFILE_FULL, PROFILE_CORE) else PROFILE_FULL
        self.supports_embedded_preview = self._profile == PROFILE_FULL
        title = GUI_DISPLAY_NAME
        if self._profile == PROFILE_CORE:
            title = f"{GUI_DISPLAY_NAME}{GUI_CORE_DISPLAY_SUFFIX}"
        self.setWindowTitle(title)
        self.setMinimumSize(1000, 700)
        self.current_theme = "light"
        self.is_diagnosing = False
        self.current_worker: Optional[object] = None
        self._progress_coalescer: Optional[object] = None
        self._deferred_hosts: Dict[int, DeferredTabHost] = {}
        self.report_viewer: Optional[QWidget] = None
        self.setup_ui()
        self.setup_menu()
        ThemeManager.apply_theme(self.current_theme)

    def setup_ui(self) -> None:
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # 首屏仅加载轻量页；诊断页首次切换时再 import 重型依赖
        from sdwan_desktop.interface.gui.tabs.tools_tab import ToolsTab

        self.tools_tab = ToolsTab()

        self.tab_widget.addTab(self.tools_tab, "网络工具")
        self._add_deferred_tab("一键体检", self._create_quick_check_tab)
        self._add_deferred_tab("深度诊断", self._create_deep_dive_tab)
        self._add_deferred_tab("业务路径诊断", self._create_business_diagnose_tab)
        if self._profile == PROFILE_FULL:
            self._add_deferred_tab("业务监测", self._create_waterfall_tab)
            from sdwan_desktop.interface.gui.widgets.report_viewer import ReportViewer

            self.report_viewer = ReportViewer()
            self.tab_widget.addTab(self.report_viewer, "报告预览")

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_current_diagnosis)

        self.status_bar.addWidget(self.status_label)
        self.status_bar.addPermanentWidget(self.cancel_btn)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # 默认页（网络工具）无需延迟
        self._on_tab_changed(self.tab_widget.currentIndex())

    def _add_deferred_tab(self, title: str, factory) -> None:
        host = DeferredTabHost(factory)
        idx = self.tab_widget.addTab(host, title)
        self._deferred_hosts[idx] = host

    @staticmethod
    def _create_quick_check_tab():
        from sdwan_desktop.interface.gui.tabs.quick_check_tab import QuickCheckTab

        return QuickCheckTab()

    @staticmethod
    def _create_business_diagnose_tab():
        from sdwan_desktop.interface.gui.tabs.business_diagnose_tab import BusinessDiagnoseTab

        return BusinessDiagnoseTab()

    @staticmethod
    def _create_deep_dive_tab():
        from sdwan_desktop.interface.gui.tabs.deep_dive_tab import DeepDiveTab

        return DeepDiveTab()

    @staticmethod
    def _create_waterfall_tab():
        from sdwan_desktop.interface.gui.tabs.waterfall_tab import WaterfallTab

        return WaterfallTab()

    def _resolve_tab_widget(self, index: int) -> Optional[QWidget]:
        widget = self.tab_widget.widget(index)
        if isinstance(widget, DeferredTabHost):
            return widget.ensure_loaded()
        return widget

    def _wire_diagnosis_tab(self, tab: QWidget) -> None:
        if hasattr(tab, "attach_main_window"):
            tab.attach_main_window(self)
        if hasattr(tab, "diagnosis_started"):
            tab.diagnosis_started.connect(self.begin_diagnosis)

    def _on_tab_changed(self, index: int) -> None:
        if index < 0:
            return
        host = self._deferred_hosts.get(index)
        if host is not None and host.inner() is None:
            tab = host.ensure_loaded()
            self._wire_diagnosis_tab(tab)

    def _tab_by_type(self, cls_name: str) -> Optional[QWidget]:
        for idx in range(self.tab_widget.count()):
            w = self._resolve_tab_widget(idx)
            if w is not None and w.__class__.__name__ == cls_name:
                return w
        return None

    @property
    def quick_check_tab(self):
        return self._tab_by_type("QuickCheckTab")

    @property
    def business_diagnose_tab(self):
        return self._tab_by_type("BusinessDiagnoseTab")

    @property
    def deep_dive_tab(self):
        return self._tab_by_type("DeepDiveTab")

    @property
    def waterfall_tab(self):
        return self._tab_by_type("WaterfallTab")

    def setup_menu(self) -> None:
        menubar = self.menuBar()
        view_menu = menubar.addMenu("视图")

        theme_action = QAction("切换主题", self)
        theme_action.setShortcut("Ctrl+T")
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)

    def toggle_theme(self) -> None:
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        ThemeManager.apply_theme(self.current_theme)
        self.status_label.setText(
            f"已切换到{'深色' if self.current_theme == 'dark' else '浅色'}主题"
        )

    def begin_diagnosis(self, worker: object) -> None:
        from sdwan_desktop.interface.gui.progress_coalescer import connect_worker_progress

        self.end_diagnosis()
        self.current_worker = worker
        self.is_diagnosing = True
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("诊断进行中…")
        self._progress_coalescer = connect_worker_progress(
            worker, self._apply_worker_progress
        )

    def _apply_worker_progress(self, percent: int, text: str) -> None:
        """与各 Tab 内进度条共用同一进度/状态源（底栏）。"""
        self.progress_bar.setValue(int(percent))
        if text:
            self.status_label.setText(text)

    def end_diagnosis(self, worker: object | None = None) -> None:
        coalescer = getattr(self, "_progress_coalescer", None)
        if coalescer is not None:
            coalescer.stop()
            self._progress_coalescer = None
        self.is_diagnosing = False
        self.current_worker = None
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("就绪")

    def open_report_preview(
        self,
        path: Path,
        *,
        switch_tab: bool = True,
        offer_save: bool = False,
    ) -> None:
        if path.suffix.lower() != ".html":
            self.status_label.setText(f"报告已生成（非 HTML）: {path.name}")
            return
        if offer_save:
            dest, _ = QFileDialog.getSaveFileName(
                self,
                "保存报告",
                path.name,
                "HTML (*.html);;All (*)",
            )
            if dest:
                Path(dest).write_bytes(path.read_bytes())
                path = Path(dest)
                self.status_label.setText(f"已保存: {path.name}")
        if not self.supports_embedded_preview or self.report_viewer is None:
            open_html_externally(path)
            self.status_label.setText(f"已在浏览器打开: {path.name}")
            return
        self.report_viewer.load_from_path(path)
        if switch_tab:
            idx = self.tab_widget.indexOf(self.report_viewer)
            if idx >= 0:
                self.tab_widget.setCurrentIndex(idx)

    def cancel_current_diagnosis(self) -> None:
        if self.current_worker:
            cancel = getattr(self.current_worker, "cancel", None)
            if callable(cancel):
                cancel()
            self.end_diagnosis()
            self.status_label.setText("诊断已取消")

    def closeEvent(self, event) -> None:
        if self.is_diagnosing:
            reply = QMessageBox.question(
                self,
                "确认退出",
                "当前有诊断任务正在执行，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.cancel_current_diagnosis()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main() -> None:
    from sdwan_desktop.core.subprocess_platform import ensure_gui_stdio
    from sdwan_desktop.interface.gui.cli_runner import configure_gui_cli_profile, PROFILE_FULL

    configure_gui_cli_profile(PROFILE_FULL)
    ensure_gui_stdio()
    configure_platform_icon()
    app = QApplication([])
    app.setApplicationName(GUI_DISPLAY_NAME)
    app.setApplicationDisplayName(GUI_DISPLAY_NAME)
    window = MainWindow(profile=PROFILE_FULL)
    apply_app_icon(app, window)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
