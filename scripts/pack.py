# scripts/pack.py
import os
import zipfile
import shutil
from datetime import datetime

def create_portable_zip():
    """创建便携版压缩包"""
    # 修复路径逻辑：pack.py 位于 scripts/ 目录下，需要返回上一级获取项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    dist_dir = os.path.join(project_root, 'dist')
    output_zip = os.path.join(project_root, 'sdwan-diagnostic-portable.zip')
    
    if not os.path.exists(dist_dir):
        print(f"Error: Dist directory not found at {dist_dir}")
        return

    version = "0.1.0-alpha"  # 可以从 pyproject.toml 动态读取
    zip_name = f"sdwan-diagnostic-{version}-portable"
    
    print(f"Creating portable package: {output_zip}")
    
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.join(zip_name, os.path.relpath(file_path, dist_dir))
                zipf.write(file_path, arcname)
                
        # 包含 configs 和 templates
        for folder in ['configs', 'templates']:
            folder_path = os.path.join(project_root, folder)
            if os.path.exists(folder_path):
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join(zip_name, os.path.relpath(file_path, project_root))
                        zipf.write(file_path, arcname)

    print(f"Portable package created successfully: {output_zip}")

if __name__ == '__main__':
    create_portable_zip()
