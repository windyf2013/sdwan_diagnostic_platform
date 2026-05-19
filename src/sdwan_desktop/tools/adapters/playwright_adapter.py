"""
Playwright适配器 - 封装浏览器启动、导航和HAR录制逻辑

提供统一的异步接口供 HarCaptureTool 调用。
"""

import logging
import os
from typing import List, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

# 隐藏 Playwright 默认在 ``navigator.webdriver`` / Chrome DevTools Protocol 标志，降低门户级网站
# 基于 ``--enable-automation`` 与 ``navigator.webdriver`` 触发的拒连/JS 挑战风险。仍保留无头模式本身的
# 指纹差异；如需更接近真人，请改用 ``headless=False``。
_STEALTH_LAUNCH_ARGS: tuple[str, ...] = (
    "--disable-blink-features=AutomationControlled",
    "--disable-features=AutomationControlled,IsolateOrigins,site-per-process",
    "--no-default-browser-check",
    "--no-first-run",
)

# 通过 ``add_init_script`` 在每个新页面上下文中执行的反指纹脚本：覆盖 navigator.webdriver、
# 修补 navigator.plugins/languages，避免最常见的「headless 检测」分支。
_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
if (navigator.plugins && navigator.plugins.length === 0) {
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
}
window.chrome = window.chrome || { runtime: {} };
"""


class PlaywrightAdapter:
    """Playwright适配器
    
    负责管理Playwright实例、浏览器上下文和页面导航。
    """

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    @staticmethod
    def _resolve_proxy(explicit: Optional[str]) -> Optional[str]:
        """按优先级解析代理：显式参数 > HTTPS_PROXY > HTTP_PROXY。返回 ``None`` 时不配置代理。"""
        if explicit and explicit.strip():
            return explicit.strip()
        for env_name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
            value = os.environ.get(env_name)
            if value and value.strip():
                return value.strip()
        return None

    async def initialize(
        self,
        headless: bool = True,
        *,
        proxy: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
    ) -> None:
        """初始化Playwright并启动浏览器

        Args:
            headless: 是否以无头模式运行。
            proxy: 代理 URL（如 ``http://127.0.0.1:7890``）。为空时按 ``HTTPS_PROXY``/``HTTP_PROXY``
                环境变量回退；均无则不配置代理。
            extra_args: 追加给 Chromium 的命令行参数；用于业务侧临时调参。
        """
        if self._browser:
            return

        launch_args = list(_STEALTH_LAUNCH_ARGS)
        if extra_args:
            launch_args.extend(a for a in extra_args if a)

        launch_kwargs: dict = {
            "headless": headless,
            "args": launch_args,
        }
        proxy_server = self._resolve_proxy(proxy)
        if proxy_server:
            launch_kwargs["proxy"] = {"server": proxy_server}
            logger.info("Playwright Chromium 使用代理: %s", proxy_server)

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        logger.info(
            "Playwright Chromium browser started (headless=%s, proxy=%s).",
            headless,
            bool(proxy_server),
        )

    async def _prepare_context(self, har_path: str) -> None:
        """创建带 HAR 录制、隐身脚本与真实浏览器伪装的上下文（供 navigate 系列复用）。"""
        if not self._browser:
            raise RuntimeError("Browser not initialized. Call initialize() first.")

        self._context = await self._browser.new_context(
            record_har_path=har_path,
            record_har_mode="full",
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            permissions=["geolocation"],
        )
        await self._context.set_extra_http_headers({
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        # 反指纹脚本必须先于业务页面 JS 注入，否则门户站点首屏 JS 已经读到 navigator.webdriver=true。
        await self._context.add_init_script(_STEALTH_INIT_SCRIPT)
        self._page = await self._context.new_page()

    async def navigate(
        self,
        url: str,
        har_path: str,
        timeout: int = 60000,
        wait_until: str = "load",
    ) -> None:
        """导航到指定URL并录制HAR

        Args:
            url: 目标URL
            har_path: HAR文件保存路径
            timeout: 页面加载超时时间(ms)
            wait_until: 等待条件 (``load`` | ``domcontentloaded`` | ``networkidle``)。
                **默认 ``load``**：在持续后台流量的站点上，``networkidle`` 易整体超时；``load`` 命中后
                仍会再次尝试 ``networkidle``/固定等待，兼顾兼容性与速率。
        """
        await self._prepare_context(har_path)
        assert self._page is not None  # for type checker

        logger.info(f"Navigating to {url} with HAR recording (wait_until={wait_until})...")

        request_count = 0
        response_count = 0

        def on_request(request):
            nonlocal request_count
            request_count += 1
            logger.debug(f"[Request #{request_count}] {request.method} {request.url}")

        def on_response(response):
            nonlocal response_count
            response_count += 1
            logger.debug(f"[Response #{response_count}] {response.status} {response.url}")

        self._page.on("request", on_request)
        self._page.on("response", on_response)

        try:
            await self._page.goto(url, timeout=timeout, wait_until=wait_until)
            logger.info(f"Initial navigation completed. Requests so far: {request_count}")
        except Exception as e:
            logger.warning(f"Navigation error (may be due to redirects): {e}")
            logger.info(f"Requests captured so far: {request_count}")

        # 即便 wait_until=load 仍尝试追加一次 networkidle / 短延时：捕获 lazy-loaded / XHR 资源。
        try:
            await self._page.wait_for_load_state("networkidle", timeout=5000)
        except Exception as e:
            logger.warning(f"Timeout waiting for networkidle: {e}")
        await self._page.wait_for_timeout(5000)

        logger.info(
            f"Navigation fully completed for {url}. "
            f"Total requests: {request_count}, responses: {response_count}"
        )

    async def navigate_with_load_strategy(
        self,
        url: str,
        har_path: str,
        timeout: int = 60000,
    ) -> None:
        """使用load事件策略导航并录制HAR（备用：对动态加载页更友好）。"""
        await self._prepare_context(har_path)
        assert self._page is not None

        logger.info(f"Navigating to {url} with load strategy...")

        request_count = 0

        def on_request(request):
            nonlocal request_count
            request_count += 1

        self._page.on("request", on_request)

        await self._page.goto(url, timeout=timeout, wait_until="load")
        logger.info(f"Load event fired. Requests so far: {request_count}")

        for state in ("domcontentloaded", "networkidle"):
            try:
                await self._page.wait_for_load_state(state, timeout=5000)
            except Exception:
                pass

        logger.info("Waiting 10s for all async resources...")
        await self._page.wait_for_timeout(10000)

        logger.info(f"Navigation completed. Total requests: {request_count}")

    async def screenshot(self, path: str) -> None:
        """截取当前页面快照
        
        Args:
            path: 截图保存路径
        """
        if self._page:
            await self._page.screenshot(path=path)
            logger.info(f"Screenshot saved to {path}")

    async def close(self) -> None:
        """关闭浏览器并释放资源"""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Playwright resources released.")
