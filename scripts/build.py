# scripts/build.py
import sys
import os
import time
import shutil
import PyInstaller.__main__

def main():
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)
    
    # 确保在正确的目录下运行
    os.chdir(project_root)

    # 清理所有 __pycache__ 目录和 .pyc 文件
    print("清理 Python 缓存文件...")
    for root, dirs, files in os.walk(project_root):
        # 删除 __pycache__ 目录
        if '__pycache__' in dirs:
            cache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(cache_path)
                print(f"已删除: {cache_path}")
            except Exception as e:
                print(f"警告: 无法删除 {cache_path}: {e}")
        
        # 删除 .pyc 文件
        for file in files:
            if file.endswith('.pyc'):
                pyc_path = os.path.join(root, file)
                try:
                    os.remove(pyc_path)
                except Exception as e:
                    print(f"警告: 无法删除 {pyc_path}: {e}")

    # 使用 spec 文件或者更明确的入口点配置
    entry_point = 'src/sdwan_desktop/interface/gui/main_window.py'

    args = [
        entry_point,
        '--name=sdwan-diagnostic-gui',
        '--onefile',
        '--windowed',
        '--icon=assets/icon.ico',
        '--paths=src',  # 显式指定 src 为搜索路径
        '--add-data=configs;configs',
        '--add-data=src/sdwan_desktop/reporting/templates;sdwan_desktop/reporting/templates',
        '--hidden-import=paramiko',
        '--hidden-import=playwright',
        '--hidden-import=jinja2',
        '--hidden-import=pyside6',
        '--hidden-import=wmi',
        '--hidden-import=sdwan_desktop',
        # GeoIP功能相关依赖(可选)
        '--hidden-import=geoip2',
        '--hidden-import=maxminddb',
        '--clean',
        '--distpath=dist',
        '--workpath=build',
        '--specpath=.',
    ]

    print(f"Starting PyInstaller build from: {os.getcwd()}")
    print(f"Entry point: {entry_point}")
    
    # 尝试清理旧文件以避免权限问题
    dist_path = os.path.join(project_root, 'dist')
    exe_path = os.path.join(dist_path, 'sdwan-diagnostic-gui.exe')
    if os.path.exists(exe_path):
        try:
            os.remove(exe_path)
            print(f"Removed old executable: {exe_path}")
        except PermissionError:
            print(f"Warning: Could not remove old executable. It might be in use. Retrying in a moment...")
            time.sleep(1) # 等待一下让系统释放文件句柄

    PyInstaller.__main__.run(args)
    print("Build completed successfully.")

if __name__ == '__main__':
    main()




