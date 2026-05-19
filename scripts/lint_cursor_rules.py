#!/usr/bin/env python3
"""Lint cursor rules layout — run: python scripts/lint_cursor_rules.py"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []

def _lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else 0

def _fail(msg: str) -> None:
    ERRORS.append(msg)

def check_ai_spec() -> None:
    p = ROOT / ".cursor" / "AI_SPEC_GUIDE.md"
    if _lines(p) > 60:
        _fail(f"AI_SPEC_GUIDE.md has {_lines(p)} lines (max 60)")
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    if "## 架构与三条功能流" in text:
        _fail("AI_SPEC_GUIDE must not contain flow checklist body")
    if "<system-reminder>" in text:
        _fail("AI_SPEC_GUIDE must not contain system-reminder")

def check_index() -> None:
    if _lines(ROOT / "memory-bank" / "INDEX.md") > 85:
        _fail("INDEX.md over 85 lines")

def check_active_context() -> None:
    p = ROOT / "memory-bank" / "activeContext.md"
    if p.is_file() and _lines(p) > 20:
        _fail("activeContext.md must be redirect only")

def check_p0() -> None:
    rules = list((ROOT / ".cursor" / "rules").glob("sdwan-p0-core.*"))
    if not rules:
        _fail("missing sdwan-p0-core rule file")
        return
    text = rules[0].read_text(encoding="utf-8")
    if "alwaysApply: true" not in text:
        _fail("sdwan-p0-core needs alwaysApply: true")
    n_always = 0
    for p in (ROOT / ".cursor" / "rules").glob("*"):
        if p.is_file() and "alwaysApply: true" in p.read_text(encoding="utf-8"):
            n_always += 1
    if n_always > 1:
        _fail(f"multiple alwaysApply rules: {n_always}")

def check_p1() -> None:
    p = ROOT / ".cursor" / "rules" / "P1-three-flows-shared.md"
    if not p.is_file():
        _fail("missing P1-three-flows-shared.md")

def main() -> int:
    check_ai_spec()
    check_index()
    check_active_context()
    check_p0()
    check_p1()
    if ERRORS:
        print("FAILED:", *ERRORS, sep="\n  - ")
        return 1
    print("OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
