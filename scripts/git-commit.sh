#!/usr/bin/env bash
# Run prepare_git_commit.py then git commit. Usage from repo root:
#   ./scripts/git-commit.sh -m "fix: probe timeout"
# Full pre-commit (slow):
#   ./scripts/git-commit.sh --pre-commit-all -m "chore: hooks"

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PRE_ARGS=(python scripts/prepare_git_commit.py --auto-add-index)
if [[ "${1:-}" == "--pre-commit-all" ]]; then
  PRE_ARGS+=(--pre-commit-all)
  shift
fi

"${PRE_ARGS[@]}"

if [[ $# -eq 0 ]]; then
  echo "usage: $0 [--pre-commit-all] git-commit-args..." >&2
  echo "example: $0 -m \"fix: description\"" >&2
  exit 2
fi

git commit "$@"
