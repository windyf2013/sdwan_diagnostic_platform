"""
清理 Python 缓存文件脚本

在打包前运行此脚本，确保使用最新的源代码。
删除所有 __pycache__ 目录和 .pyc 文件。
"""

import os
import shutil


def clean_pycache(root_dir: str):
    """清理指定目录下的所有 Python 缓存文件"""
    cleaned_dirs = 0
    cleaned_files = 0
    
    for root, dirs, files in os.walk(root_dir):
        # 删除 __pycache__ 目录
        if '__pycache__' in dirs:
            cache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(cache_path)
                cleaned_dirs += 1
                print(f"已删除目录: {cache_path}")
            except Exception as e:
                print(f"警告: 无法删除 {cache_path}: {e}")
        
        # 删除 .pyc 文件
        for file in files:
            if file.endswith('.pyc'):
                pyc_path = os.path.join(root, file)
                try:
                    os.remove(pyc_path)
                    cleaned_files += 1
                except Exception as e:
                    print(f"警告: 无法删除 {pyc_path}: {e}")
    
    print(f"\n清理完成！")
    print(f"  - 删除了 {cleaned_dirs} 个 __pycache__ 目录")
    print(f"  - 删除了 {cleaned_files} 个 .pyc 文件")


if __name__ == '__main__':
    # 获取项目根目录（脚本所在目录的上级）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    print(f"开始清理项目: {project_root}")
    print("=" * 60)
    
    clean_pycache(project_root)
    
    print("=" * 60)
    print("建议接下来执行以下操作：")
    print("1. 删除 build 和 dist 目录（可选，但推荐）")
    print("2. 重新运行打包脚本: python scripts/build.py")
