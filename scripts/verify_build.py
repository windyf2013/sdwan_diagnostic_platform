# scripts/verify_build.py
import os
import sys

def check_version():
    """检查版本信息"""
    try:
        # 修复路径逻辑：verify_build.py 位于 scripts/ 目录下
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        
        dist_dir = os.path.join(project_root, 'dist')
        exe_path = os.path.join(dist_dir, 'sdwan-diagnostic-gui.exe')
        
        if not os.path.exists(exe_path):
            print(f"[FAIL] Executable not found: {exe_path}")
            return False
            
        file_size = os.path.getsize(exe_path) / (1024 * 1024)  # MB
        print(f"[PASS] Executable exists: {exe_path}")
        print(f"       Size: {file_size:.2f} MB")
        
        if file_size > 200:
            print(f"[WARN] File size exceeds 200MB limit")
        else:
            print(f"[PASS] File size is within limits (<200MB)")
            
        return True
    except Exception as e:
        print(f"[ERROR] Version check failed: {e}")
        return False

def check_cli_entry():
    """检查 CLI 入口点"""
    try:
        # 验证核心模块是否可以被导入
        from sdwan_desktop.interface.cli.commands.quick_check import quick_check
        from sdwan_desktop.interface.cli.commands.deep_dive import deep_dive
        from sdwan_desktop.interface.cli.commands.waterfall import waterfall
        print("[PASS] CLI commands modules import successful")
        return True
    except Exception as e:
        print(f"[FAIL] CLI module import failed: {e}")
        return False

def main():
    print("=== SD-WAN Diagnostic Platform Build Verification ===")
    success = True
    success &= check_version()
    success &= check_cli_entry()
    
    if success:
        print("\n[SUCCESS] All verification checks passed!")
    else:
        print("\n[FAILURE] Some verification checks failed.")
        sys.exit(1)

if __name__ == '__main__':
    main()
