# scripts/verify_build.py
"""打包产物校验：模块、模板、PyInstaller warn、Playwright 浏览器与体积。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# pydantic 在 warn 中常误报为 missing submodule
_WARN_IGNORE_SUBSTRINGS = (
    "pydantic.BaseModel",
    "pydantic.deprecated",
    "pydantic.v1",
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _dir_size_mb(path: Path) -> float:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def _gui_dist_names() -> tuple[str, str]:
    root = _project_root()
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from sdwan_desktop.interface.gui.app_branding import GUI_EXECUTABLE_NAME

    name = GUI_EXECUTABLE_NAME
    exe_name = f"{name}.exe" if os.name == "nt" else name
    return name, exe_name


def check_gui_bundle(max_folder_mb: float = 450.0) -> bool:
    """GUI 为 onedir（含 Qt WebEngine + Playwright driver + 外置 Chromium）。"""
    gui_dir_name, gui_exe_name = _gui_dist_names()
    folder = _project_root() / "dist" / gui_dir_name
    exe = folder / gui_exe_name
    if not exe.is_file():
        legacy = _project_root() / "dist" / gui_exe_name
        if legacy.is_file():
            size_mb = legacy.stat().st_size / (1024 * 1024)
            print(
                f"[WARN] 仍为旧版 onefile GUI ({size_mb:.1f} MB)，"
                "请运行 python scripts/build.py 重建 onedir"
            )
            return False
        print(f"[FAIL] GUI not found: {exe}")
        return False

    size_mb = _dir_size_mb(folder)
    print(f"[PASS] GUI onedir: {folder} ({size_mb:.1f} MB total)")
    if size_mb > max_folder_mb:
        print(f"[WARN] GUI folder exceeds {max_folder_mb:.0f} MB (含 WebEngine/Playwright 时属正常)")
    return True


def check_executable(name: str, max_mb: float = 200.0) -> bool:
    exe = _project_root() / "dist" / (f"{name}.exe" if os.name == "nt" else name)
    if not exe.is_file():
        print(f"[FAIL] Executable not found: {exe}")
        return False
    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"[PASS] {name}: {exe} ({size_mb:.1f} MB)")
    if size_mb > max_mb:
        print(f"[WARN] {name} exceeds {max_mb:.0f} MB")
    return True


def check_playwright_browsers() -> bool:
    browser_dir = _project_root() / "dist" / "ms-playwright"
    if not browser_dir.is_dir():
        print(f"[FAIL] Playwright browsers missing: {browser_dir}")
        print("       Run: python scripts/build.py (includes playwright install chromium)")
        return False
    if not any(browser_dir.rglob("chrome.exe")) and not any(browser_dir.rglob("chromium")):
        print(f"[FAIL] No Chromium binary under {browser_dir}")
        return False
    print(f"[PASS] Playwright Chromium present under {browser_dir}")
    return True


def _parse_warn_issues(text: str) -> list[str]:
    issues: list[str] = []
    for line in text.splitlines():
        lower = line.lower()
        if "sdwan_desktop" not in line:
            continue
        if any(ign in line for ign in _WARN_IGNORE_SUBSTRINGS):
            continue
        if "excluded module named playwright" in lower:
            issues.append(line.strip())
        elif "missing module" in lower and "sdwan_desktop" in line:
            issues.append(line.strip())
    return issues


def check_pyinstaller_warns() -> bool:
    """扫描 PyInstaller warn 文件，确认未错误排除 Playwright 或遗漏 sdwan 模块。"""
    gui_dir_name, _gui_exe_name = _gui_dist_names()
    warn_paths = [
        _project_root() / "build" / "gui" / gui_dir_name / f"warn-{gui_dir_name}.txt",
        _project_root() / "build" / "cli" / "agentctl" / "warn-agentctl.txt",
    ]
    ok = True
    for path in warn_paths:
        if not path.is_file():
            print(f"[WARN] warn file not found (build first): {path}")
            continue
        issues = _parse_warn_issues(path.read_text(encoding="utf-8", errors="replace"))
        if issues:
            ok = False
            print(f"[FAIL] {path.name}:")
            for item in issues[:8]:
                print(f"       {item}")
            if len(issues) > 8:
                print(f"       ... and {len(issues) - 8} more")
        else:
            print(f"[PASS] {path.name}: no sdwan_desktop/playwright packaging issues")
    return ok


def check_hidden_import_names() -> bool:
    """构建脚本应使用 PySide6 / dns，且包含 Playwright、不 exclude playwright。"""
    build_py = (_project_root() / "scripts" / "build.py").read_text(encoding="utf-8")
    required_snippets = ('"PySide6"', '"dns"', "PLAYWRIGHT_HIDDEN_IMPORTS", "--collect-all=playwright")
    missing = [s for s in required_snippets if s not in build_py]
    if '"playwright"' in build_py and 'exclude-module=playwright' in build_py.replace(" ", ""):
        missing.append("playwright must not be in --exclude-module")
    if missing:
        print(f"[FAIL] build.py config: missing or wrong {missing}")
        return False
    print("[PASS] build.py uses PySide6, dns, and includes Playwright")
    return True


def check_core_flow_imports() -> bool:
    src = _project_root() / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from sdwan_desktop.interface.cli.commands.quick_check import quick_check  # noqa: F401
        from sdwan_desktop.interface.cli.commands.deep_dive import deep_dive  # noqa: F401
        from sdwan_desktop.interface.cli.commands.business_diagnose import business_diagnose  # noqa: F401
        from sdwan_desktop.core.subprocess_platform import run_hidden  # noqa: F401
        from sdwan_desktop.tools.implementations.web import har_capture  # noqa: F401
        print("[PASS] Core flow + Playwright HAR modules import OK")
        return True
    except Exception as exc:
        print(f"[FAIL] Core flow import failed: {exc}")
        return False


def check_report_templates() -> bool:
    template_dir = _project_root() / "src" / "sdwan_desktop" / "reporting" / "templates"
    required = [
        "quick_check.html",
        "deep_dive.html",
        "deep_dive_joint_ux.html",
        "business_diagnosis.html",
    ]
    missing = [n for n in required if not (template_dir / n).is_file()]
    if missing:
        print(f"[FAIL] Missing templates: {missing}")
        return False
    print(f"[PASS] Report templates OK ({len(required)} files)")
    return True


def main() -> None:
    print("=== SD-WAN Build Verification ===\n")
    ok = True
    ok &= check_hidden_import_names()
    ok &= check_core_flow_imports()
    ok &= check_report_templates()
    ok &= check_pyinstaller_warns()
    ok &= check_playwright_browsers()
    ok &= check_gui_bundle()
    ok &= check_executable("agentctl", max_mb=250.0)
    if ok:
        print("\n[SUCCESS] All verification checks passed.")
    else:
        print("\n[FAILURE] Some verification checks failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
