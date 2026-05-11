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

        # 创建带HAR录制的上下文，配置更真实的浏览器环境
        self._context = await self._browser.new_context(
            record_har_path=har_path,
            record_har_mode="full",  # 录制所有请求，包括重定向
            ignore_https_errors=True,  # 忽略HTTPS错误
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},  # 标准桌面分辨率
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            permissions=["geolocation"],  # 授予地理位置权限
        )
        
        # 设置额外的headers来模拟真实浏览器
        await self._context.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
        self._page = await self._context.new_page()
        
        logger.info(f"Navigating to {url} with HAR recording...")
        
        # 监听所有请求和响应，用于调试
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
        
        # 执行导航
        logger.info(f"Starting navigation to {url}...")
        try:
            await self._page.goto(url, timeout=timeout, wait_until=wait_until)
            logger.info(f"Initial navigation completed. Requests so far: {request_count}")
        except Exception as e:
            logger.warning(f"Navigation error (may be due to redirects): {e}")
            logger.info(f"Requests captured so far: {request_count}")
        
        # 等待额外的网络空闲，确保捕获所有异步资源
        logger.info("Waiting for additional network idle (5s)...")
        try:
            await self._page.wait_for_load_state("networkidle", timeout=5000)
        except Exception as e:
            logger.warning(f"Timeout waiting for networkidle: {e}")
        
        # 再等待5秒，给JavaScript异步请求时间
        logger.info("Waiting 5s for async/deferred resources...")
        await self._page.wait_for_timeout(5000)
        
        logger.info(f"Navigation fully completed for {url}. Total requests: {request_count}, responses: {response_count}")

    async def navigate_with_load_strategy(
        self, 
        url: str, 
        har_path: str, 
        timeout: int = 60000
    ) -> None:
        """使用load事件策略导航并录制HAR
        
        这种策略更适合动态加载的页面，通过等待load事件后额外等待来捕获所有资源。
        
        Args:
            url: 目标URL
            har_path: HAR文件保存路径
            timeout: 页面加载超时时间(ms)
        """
        if not self._browser:
            raise RuntimeError("Browser not initialized. Call initialize() first.")

        # 创建带HAR录制的上下文，配置更真实的浏览器环境
        self._context = await self._browser.new_context(
            record_har_path=har_path,
            record_har_mode="full",
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            permissions=["geolocation"],
        )
        
        # 设置额外的headers来模拟真实浏览器
        await self._context.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
        self._page = await self._context.new_page()
        
        logger.info(f"Navigating to {url} with load strategy...")
        
        # 监听请求
        request_count = 0
        def on_request(request):
            nonlocal request_count
            request_count += 1
        
        self._page.on("request", on_request)
        
        # 先等待load事件（比networkidle更快触发）
        await self._page.goto(url, timeout=timeout, wait_until="load")
        logger.info(f"Load event fired. Requests so far: {request_count}")
        
        # 等待DOM内容完全加载
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
        except:
            pass
        
        # 等待网络空闲
        try:
            await self._page.wait_for_load_state("networkidle", timeout=5000)
        except:
            pass
        
        # 长时间等待，确保所有异步资源都被捕获
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
