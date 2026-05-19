"""完整版 CLI 入口：在核心子命令基础上增加 waterfall（Playwright HAR）。"""

from __future__ import annotations

from sdwan_desktop.core.app_paths import configure_playwright_browsers_path
from sdwan_desktop.interface.cli.bootstrap import build_core_cli
from sdwan_desktop.interface.cli.commands.waterfall import waterfall

configure_playwright_browsers_path()

main = build_core_cli()
main.add_command(waterfall)

if __name__ == "__main__":
    main()
