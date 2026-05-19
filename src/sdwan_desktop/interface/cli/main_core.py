"""核心版 CLI 入口：不含 waterfall / Playwright（供 core GUI 与 agentctl-core 使用）。"""

from __future__ import annotations

from sdwan_desktop.interface.cli.bootstrap import build_core_cli

main = build_core_cli()

if __name__ == "__main__":
    main()
