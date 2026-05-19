# scripts/build.py
"""构建入口：请使用 build_full.py（完整版）或 build_core.py（核心版）。"""
from __future__ import annotations

import sys


def main() -> None:
    print(
        "请选择构建脚本:\n"
        "  python scripts/build_full.py   # 完整功能，onedir + 外挂 ms-playwright\n"
        "  python scripts/build_core.py   # 核心功能，onefile，无业务监测/内嵌预览\n"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
