import sys
import os

# 修复 PyInstaller 打包后的相对导入问题
if getattr(sys, 'frozen', False):
    # 如果是打包后的 exe，将可执行文件所在目录加入路径
    application_path = os.path.dirname(sys.executable)
else:
    # 如果是直接运行 python 脚本
    application_path = os.path.dirname(os.path.abspath(__file__))

# 确保 src 目录在 sys.path 中
src_path = os.path.join(os.path.dirname(application_path), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from .main_window import MainWindow, main

__all__ = ["MainWindow", "main"]
