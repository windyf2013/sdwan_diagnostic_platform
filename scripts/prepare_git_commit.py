#!/usr/bin/env python3
"""Run repository-required steps before ``git commit``.

Default steps:
  1. Regenerate ``docs/implementation/SRC_INDEX.md`` (see
     implementation_doc_mirror / pre-commit).
  2. Run pre-commit hook ``implementation-src-index`` (``--check`` on index).

Options:
  ``--auto-add-index`` — if ``SRC_INDEX.md`` changed, ``git add`` that file.
  ``--pre-commit-all`` — then run ``pre-commit run --all-files`` (slow).

Exits non-zero on failure. Does not run ``git commit``; use
``scripts/git-commit.ps1`` / ``git-commit.sh`` or commit manually.

Usage (repo root)::

    python scripts/prepare_git_commit.py
    python scripts/prepare_git_commit.py --auto-add-index
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_FALLBACK = SCRIPT_DIR.parent


def _run(cmd: list[str], *, cwd: Path) -> None:
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def _git_output(args: list[str], cwd: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def _repo_root() -> Path:
    cwd = Path.cwd()
    top = _git_output(["rev-parse", "--show-toplevel"], cwd)
    if top:
        return Path(top)
    top2 = _git_output(["rev-parse", "--show-toplevel"], REPO_FALLBACK)
    if top2:
        return Path(top2)
    return REPO_FALLBACK


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--auto-add-index",
        action="store_true",
        help="Run `git add docs/implementation/SRC_INDEX.md` when its content changes.",
    )
    parser.add_argument(
        "--pre-commit-all",
        action="store_true",
        help="Run full `pre-commit run --all-files` after index hook.",
    )
    args = parser.parse_args()

    root = _repo_root()
    gen = root / "scripts" / "generate_implementation_index.py"
    index = root / "docs" / "implementation" / "SRC_INDEX.md"

    if not gen.is_file():
        print(f"error: missing generator {gen}", file=sys.stderr)
        return 1

    before = _file_sha256(index)

    try:
        _run([sys.executable, str(gen)], cwd=root)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 1

    after = _file_sha256(index)
    changed = before != after

    if args.auto_add_index and changed:
        if _git_output(["rev-parse", "--is-inside-work-tree"], root) != "true":
            print("warning: not a git work tree; skip git add", file=sys.stderr)
        else:
            _run(["git", "add", "--", "docs/implementation/SRC_INDEX.md"], cwd=root)

    # Mirror pre-commit local hook (must pass after regen)
    if not shutil.which("pre-commit"):
        print(
            "error: `pre-commit` not found on PATH. "
            "Install: pip install pre-commit && pre-commit install",
            file=sys.stderr,
        )
        return 1
    try:
        _run(
            [
                "pre-commit",
                "run",
                "implementation-src-index",
                "--all-files",
            ],
            cwd=root,
        )
    except SystemExit:
        print(
            "error: pre-commit hook implementation-src-index failed. "
            "Install dev deps (`pip install pre-commit`) or fix SRC_INDEX.",
            file=sys.stderr,
        )
        return 1

    if args.pre_commit_all:
        try:
            _run(["pre-commit", "run", "--all-files"], cwd=root)
        except SystemExit:
            print("error: pre-commit run --all-files failed.", file=sys.stderr)
            return 1

    print("prepare_git_commit: OK")
    if changed and not args.auto_add_index:
        print(
            "hint: SRC_INDEX.md changed; stage: "
            "git add docs/implementation/SRC_INDEX.md"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
