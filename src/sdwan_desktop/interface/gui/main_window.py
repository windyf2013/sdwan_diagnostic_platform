import sys
import os

# 修复 PyInstaller 打包后的模块查找问题
if getattr(sys, 'frozen', False):
    # 如果是打包后的 exe，将可执行文件所在目录加入路径
    application_path = os.path.dirname(sys.executable)
else:
    # 如果是直接运行 python 脚本
    application_path = os.path.dirname(os.path.abspath(__file__))

# 关键修复：在打包环境下，PyInstaller 会将源码解压到临时目录 _MEIxxxxxx
# 我们需要确保这个临时目录在 sys.path 中，或者手动添加项目根目录
# 通常 PyInstaller 会自动处理，但显式添加更稳妥
if application_path not in sys.path:
    sys.path.insert(0, application_path)

# 尝试多种可能的路径结构
possible_paths = [
    os.path.join(application_path, 'src'),
    os.path.join(os.path.dirname(application_path), 'src'),
    application_path
]

for path in possible_paths:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, 
    QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QStatusBar, QPushButton, QMessageBox
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

# 导入标签页组件和样式管理
from sdwan_desktop.interface.gui.tabs.tools_tab import ToolsTab
from sdwan_desktop.interface.gui.tabs.quick_check_tab import QuickCheckTab
from sdwan_desktop.interface.gui.tabs.deep_dive_tab import DeepDiveTab
from sdwan_desktop.interface.gui.tabs.waterfall_tab import WaterfallTab
from sdwan_desktop.interface.gui.widgets.report_viewer import ReportViewer
from sdwan_desktop.interface.gui.styles.theme import ThemeManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SD-WAN桌面诊断专家")
        self.setMinimumSize(1000, 700)
        self.current_theme = "light"
        self.is_diagnosing = False
        self.setup_ui()
        self.setup_menu()
        ThemeManager.apply_theme(self.current_theme)

    def setup_ui(self):
        # 中心组件：标签页
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # 预留 5 个功能标签页
        self.tools_tab = ToolsTab()
        self.quick_check_tab = QuickCheckTab()
        self.deep_dive_tab = DeepDiveTab()
        self.waterfall_tab = WaterfallTab()
        self.report_viewer = ReportViewer()

        self.tab_widget.addTab(self.tools_tab, "网络工具")
        self.tab_widget.addTab(self.quick_check_tab, "一键体检")
        self.tab_widget.addTab(self.deep_dive_tab, "深度诊断")
        self.tab_widget.addTab(self.waterfall_tab, "业务监测")
        self.tab_widget.addTab(self.report_viewer, "报告预览")

        # 底部状态栏
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

    def setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        view_menu = menubar.addMenu("视图")
        
        theme_action = QAction("切换主题", self)
        theme_action.setShortcut("Ctrl+T")
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)

    def toggle_theme(self):
        """切换浅色/深色主题"""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        ThemeManager.apply_theme(self.current_theme)
        self.status_label.setText(f"已切换到{'深色' if self.current_theme == 'dark' else '浅色'}主题")

    def cancel_current_diagnosis(self):
        """取消当前正在执行的诊断"""
        if hasattr(self, 'current_worker') and self.current_worker:
            self.current_worker.cancel()
            self.is_diagnosing = False
            self.cancel_btn.setVisible(False)
            self.progress_bar.setVisible(False)
            self.status_label.setText("诊断已取消")

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        if self.is_diagnosing:
            reply = QMessageBox.question(
                self, '确认退出', 
                '当前有诊断任务正在执行，确定要退出吗？',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.cancel_current_diagnosis()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    # 增加打包环境下的路径支持
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
        src_path = os.path.join(os.path.dirname(application_path), 'src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
    main()
