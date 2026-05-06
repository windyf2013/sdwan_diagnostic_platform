"""
Playwright适配器 - 封装浏览器启动、导航和HAR录制逻辑

提供统一的异步接口供 HarCaptureTool 调用。
"""

import logging
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class PlaywrightAdapter:
    """Playwright适配器
    
    负责管理Playwright实例、浏览器上下文和页面导航。
    """

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def initialize(self, headless: bool = True) -> None:
        """初始化Playwright并启动浏览器
        
        Args:
            headless: 是否以无头模式运行
        """
        if self._browser:
            return
            
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=headless)
        logger.info("Playwright Chromium browser started.")

    async def navigate(
        self, 
        url: str, 
        har_path: str, 
        timeout: int = 60000, 
        wait_until: str = "networkidle"
    ) -> None:
        """导航到指定URL并录制HAR
        
        Args:
            url: 目标URL
            har_path: HAR文件保存路径
            timeout: 页面加载超时时间(ms)
            wait_until: 等待条件 (load, domcontentloaded, networkidle)
        """
        if not self._browser:
            raise RuntimeError("Browser not initialized. Call initialize() first.")

        # 创建带HAR录制的上下文
        self._context = await self._browser.new_context(record_har_path=har_path)
        self._page = await self._context.new_page()
        
        logger.info(f"Navigating to {url} with HAR recording...")
        await self._page.goto(url, timeout=timeout, wait_until=wait_until)
        logger.info(f"Navigation completed for {url}")

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
