"""
全局样式管理模块
负责定义和管理 SD-WAN 诊断平台的 UI 主题与样式。
"""

from PySide6.QtWidgets import QApplication


class ThemeManager:
    """主题管理器"""
    
    LIGHT_THEME = """
        QMainWindow, QWidget {
            background-color: #f5f7fa;
            color: #2c3e50;
        }
        QTabWidget::pane {
            border: 1px solid #dcdfe6;
            background: white;
        }
        QTabBar::tab {
            background: #e4e7ed;
            color: #606266;
            padding: 8px 16px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background: #409eff;
            color: white;
        }
        QPushButton {
            background-color: #409eff;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #66b1ff;
        }
        QPushButton:disabled {
            background-color: #a0cfff;
        }
        QLineEdit, QTextEdit {
            border: 1px solid #dcdfe6;
            border-radius: 4px;
            padding: 4px;
        }
        QProgressBar {
            border: 1px solid #dcdfe6;
            border-radius: 4px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #409eff;
        }
        QTableWidget {
            border: 1px solid #dcdfe6;
            gridline-color: #ebeef5;
        }
        QHeaderView::section {
            background-color: #f5f7fa;
            padding: 4px;
            border: 1px solid #dcdfe6;
        }
    """

    DARK_THEME = """
        QMainWindow, QWidget {
            background-color: #1e1e1e;
            color: #d4d4d4;
        }
        QTabWidget::pane {
            border: 1px solid #3e3e3e;
            background: #252526;
        }
        QTabBar::tab {
            background: #2d2d2d;
            color: #cccccc;
            padding: 8px 16px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background: #007acc;
            color: white;
        }
        QPushButton {
            background-color: #007acc;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #0098ff;
        }
        QPushButton:disabled {
            background-color: #3e3e3e;
        }
        QLineEdit, QTextEdit {
            border: 1px solid #3e3e3e;
            border-radius: 4px;
            padding: 4px;
            background-color: #3c3c3c;
            color: #d4d4d4;
        }
        QProgressBar {
            border: 1px solid #3e3e3e;
            border-radius: 4px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #007acc;
        }
        QTableWidget {
            border: 1px solid #3e3e3e;
            gridline-color: #3e3e3e;
            background-color: #252526;
        }
        QHeaderView::section {
            background-color: #2d2d2d;
            padding: 4px;
            border: 1px solid #3e3e3e;
        }
    """

    @staticmethod
    def apply_theme(theme_name: str = "light"):
        """应用指定主题"""
        app = QApplication.instance()
        if not app:
            return
            
        if theme_name == "dark":
            app.setStyleSheet(ThemeManager.DARK_THEME)
        else:
            app.setStyleSheet(ThemeManager.LIGHT_THEME)
