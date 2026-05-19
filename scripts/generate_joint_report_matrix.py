#!/usr/bin/env python3
"""生成业务联合报告仿真矩阵 HTML（多组网 / 多故障目视验收）。

用法（在 sdwan_diagnostic_platform 目录下）::

    python scripts/generate_joint_report_matrix.py
    python scripts/generate_joint_report_matrix.py -o reports/sim_matrix_custom

生成后打开 ``reports/sim_matrix/index.html`` 逐场景点开 HTML 报告。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tests.simulation.joint_report_matrix import _DEFAULT_OUT, run_matrix  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="业务联合报告仿真矩阵")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=_DEFAULT_OUT,
        help=f"输出目录（默认 {_DEFAULT_OUT}）",
    )
    args = parser.parse_args()
    index, results = run_matrix(args.output)
    failed = [r for r in results if not all(r.checks.values())]
    print(f"Index: {index}")
    print(f"Reports: {len(results)} files in {args.output}")
    for r in results:
        status = "OK" if all(r.checks.values()) else "FAIL"
        print(f"  [{status}] {r.scenario_id} -> {r.rule_case} overlay={r.show_overlay}")
    if failed:
        print(f"\n{len(failed)} scenario(s) failed automated checks.", file=sys.stderr)
        return 1
    print("\nOpen index.html in a browser for visual acceptance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
