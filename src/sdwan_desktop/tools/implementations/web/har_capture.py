"""HAR捕获工具 - 网页性能分析"""

import asyncio
import json
import tempfile
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import time

from ....core.types.context import Context
from ....tools.registry.decorator import tool_function
from ....tools.registry.dispatcher import ToolRequest


@dataclass
class HarEntry:
    """HAR条目"""
    url: str
    method: str
    status: int
    content_type: str
    size: int
    timings: Dict[str, float]
    start_time: float


@dataclass
class WaterfallMetrics:
    """Waterfall性能指标"""
    page_load_time: float
    dom_content_loaded: float
    total_requests: int
    total_size_bytes: int
    slowest_resource: Optional[HarEntry]
    blocking_resources: List[HarEntry]


@dataclass
class CaptureOptions:
    """捕获选项"""
    url: str
    timeout: int = 30
    wait_for_network_idle: bool = True
    network_idle_timeout: int = 2000  # 毫秒
    viewport_width: int = 1920
    viewport_height: int = 1080
    headless: bool = True
    capture_screenshot: bool = True
    screenshot_path: Optional[str] = None


@tool_function(
    name="har_capture",
    description="网页HAR捕获与性能分析",
    timeout=120,
    retry_count=1
)
class HarCaptureTool:
    """HAR捕获工具 - 网页性能分析"""
    
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
    
    async def execute(self, request: ToolRequest, ctx: Context) -> Dict[str, Any]:
        """执行HAR捕获"""
        url = request.params.get("url", "")
        timeout = request.params.get("timeout", 30)
        wait_for_network_idle = request.params.get("wait_for_network_idle", True)
        capture_screenshot = request.params.get("capture_screenshot", True)
        
        if not url:
            return {
                "status": "error",
                "data": None,
                "error": "必须提供URL"
            }
        
        options = CaptureOptions(
            url=url,
            timeout=timeout,
            wait_for_network_idle=wait_for_network_idle,
            capture_screenshot=capture_screenshot
        )
        
        try:
            result = await self._capture_har(options)
            return {
                "status": "success",
                "data": result,
                "error": None
            }
            
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "error": f"HAR捕获失败: {str(e)}"
            }
    
    async def _capture_har(self, options: CaptureOptions) -> Dict[str, Any]:
        """捕获HAR数据"""
        from playwright.async_api import async_playwright
        
        try:
            # 初始化Playwright
            playwright = await async_playwright().start()
            self._playwright = playwright
            
            # 启动浏览器
            browser = await playwright.chromium.launch(
                headless=options.headless,
                args=[
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu'
                ]
            )
            self._browser = browser
            
            # 创建上下文
            context = await browser.new_context(
                viewport={
                    'width': options.viewport_width,
                    'height': options.viewport_height
                },
                ignore_https_errors=True
            )
            self._context = context
            
            # 创建页面
            page = await context.new_page()
            
            # 监听网络请求
            har_entries = []
            
            def on_request(request):
                """请求开始"""
                entry = HarEntry(
                    url=request.url,
                    method=request.method,
                    status=0,
                    content_type="",
                    size=0,
                    timings={
                        "blocked": -1,
                        "dns": -1,
                        "connect": -1,
                        "ssl": -1,
                        "send": -1,
                        "wait": -1,
                        "receive": -1
                    },
                    start_time=time.time()
                )
                request._har_entry = entry
                har_entries.append(entry)
            
            def on_response(response):
                """请求响应"""
                request = response.request
                if hasattr(request, '_har_entry'):
                    entry = request._har_entry
                    entry.status = response.status
                    
                    # 获取Content-Type
                    content_type = response.headers.get('content-type', '')
                    entry.content_type = content_type.split(';')[0] if content_type else ''
            
            page.on("request", on_request)
            page.on("response", on_response)
            
            # 导航到页面
            start_time = time.time()
            
            try:
                response = await page.goto(
                    options.url,
                    wait_until="networkidle" if options.wait_for_network_idle else "load",
                    timeout=options.timeout * 1000
                )
            except Exception as e:
                # 即使导航失败，也继续处理已捕获的请求
                pass
            
            # 等待网络空闲
            if options.wait_for_network_idle:
                try:
                    await page.wait_for_load_state("networkidle", timeout=options.network_idle_timeout)
                except Exception:
                    # 网络空闲超时，继续处理
                    pass
            
            # 获取页面加载时间
            page_load_time = time.time() - start_time
            
            # 获取DOM加载时间
            dom_content_loaded = await page.evaluate("() => performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart")
            
            # 获取性能指标
            performance_metrics = await page.evaluate("""
                () => {
                    const perf = performance.getEntriesByType('navigation')[0];
                    return {
                        domComplete: perf.domComplete,
                        loadEventEnd: perf.loadEventEnd,
                        responseStart: perf.responseStart,
                        requestStart: perf.requestStart
                    };
                }
            """)
            
            # 计算总大小和请求数
            total_size = 0
            for entry in har_entries:
                # 估算大小（实际需要从响应中获取）
                entry.size = 1024  # 默认值
            
            total_requests = len(har_entries)
            
            # 分析性能瓶颈
            slowest_resource = None
            blocking_resources = []
            
            if har_entries:
                # 找到最慢的资源
                max_duration = 0
                for entry in har_entries:
                    duration = sum(v for v in entry.timings.values() if v > 0)
                    if duration > max_duration:
                        max_duration = duration
                        slowest_resource = entry
                
                # 找到阻塞渲染的资源
                for entry in har_entries:
                    if entry.content_type in ['text/css', 'text/javascript', 'application/javascript']:
                        blocking_resources.append(entry)
            
            # 捕获截图
            screenshot_path = None
            if options.capture_screenshot:
                screenshot_dir = tempfile.mkdtemp(prefix="sdwan_har_")
                screenshot_path = os.path.join(screenshot_dir, "screenshot.png")
                await page.screenshot(path=screenshot_path, full_page=True)
            
            # 生成HAR数据
            har_data = self._generate_har_data(har_entries, options.url)
            
            # 计算Waterfall指标
            metrics = WaterfallMetrics(
                page_load_time=page_load_time,
                dom_content_loaded=dom_content_loaded,
                total_requests=total_requests,
                total_size_bytes=total_size,
                slowest_resource=slowest_resource,
                blocking_resources=blocking_resources
            )
            
            # 清理
            await page.close()
            await context.close()
            await browser.close()
            await playwright.stop()
            
            self._playwright = None
            self._browser = None
            self._context = None
            
            return {
                "har_data": har_data,
                "metrics": {
                    "page_load_time": metrics.page_load_time,
                    "dom_content_loaded": metrics.dom_content_loaded,
                    "total_requests": metrics.total_requests,
                    "total_size_bytes": metrics.total_size_bytes,
                    "slowest_resource": {
                        "url": metrics.slowest_resource.url if metrics.slowest_resource else None,
                        "content_type": metrics.slowest_resource.content_type if metrics.slowest_resource else None
                    } if metrics.slowest_resource else None,
                    "blocking_resources_count": len(metrics.blocking_resources)
                },
                "screenshot_path": screenshot_path,
                "performance_metrics": performance_metrics,
                "url": options.url,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            # 确保清理资源
            await self._cleanup()
            raise e
    
    def _generate_har_data(self, entries: List[HarEntry], url: str) -> Dict[str, Any]:
        """生成HAR格式数据"""
        har = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "SD-WAN诊断平台",
                    "version": "1.0.0"
                },
                "pages": [
                    {
                        "startedDateTime": datetime.now().isoformat(),
                        "id": "page_1",
                        "title": f"HAR Capture - {url}",
                        "pageTimings": {
                            "onContentLoad": -1,
                            "onLoad": -1
                        }
                    }
                ],
                "entries": []
            }
        }
        
        for i, entry in enumerate(entries):
            har_entry = {
                "startedDateTime": datetime.fromtimestamp(entry.start_time).isoformat(),
                "time": sum(v for v in entry.timings.values() if v > 0),
                "request": {
                    "method": entry.method,
                    "url": entry.url,
                    "httpVersion": "HTTP/1.1",
                    "headers": [],
                    "queryString": [],
                    "cookies": [],
                    "headersSize": -1,
                    "bodySize": -1
                },
                "response": {
                    "status": entry.status,
                    "statusText": "OK" if 200 <= entry.status < 300 else "Error",
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": "Content-Type", "value": entry.content_type}
                    ],
                    "cookies": [],
                    "content": {
                        "size": entry.size,
                        "mimeType": entry.content_type,
                        "text": ""
                    },
                    "redirectURL": "",
                    "headersSize": -1,
                    "bodySize": entry.size
                },
                "cache": {},
                "timings": entry.timings,
                "serverIPAddress": "",
                "connection": "",
                "pageref": "page_1"
            }
            
            har["log"]["entries"].append(har_entry)
        
        return har
    
    async def _cleanup(self):
        """清理资源"""
        try:
            if self._context:
                await self._context.close()
                self._context = None
        except Exception:
            pass
        
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
        except Exception:
            pass
        
        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception:
            pass
    
    async def analyze_performance(self, har_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析HAR性能数据"""
        entries = har_data.get("log", {}).get("entries", [])
        
        if not entries:
            return {
                "status": "error",
                "data": None,
                "error": "HAR数据为空"
            }
        
        # 计算性能指标
        total_time = 0
        total_size = 0
        request_count = len(entries)
        
        slowest_entry = None
        max_time = 0
        
        resource_types = {}
        
        for entry in entries:
            # 计算总时间
            entry_time = entry.get("time", 0)
            total_time += entry_time
            
            # 计算总大小
            response = entry.get("response", {})
            content = response.get("content", {})
            size = content.get("size", 0)
            total_size += size
            
            # 找到最慢的资源
            if entry_time > max_time:
                max_time = entry_time
                slowest_entry = entry
            
            # 统计资源类型
            mime_type = content.get("mimeType", "unknown")
            resource_types[mime_type] = resource_types.get(mime_type, 0) + 1
        
        # 分析瓶颈
        bottlenecks = []
        
        # DNS时间过长
        dns_slow_entries = []
        for entry in entries:
            timings = entry.get("timings", {})
            dns_time = timings.get("dns", -1)
            if dns_time > 100:  # DNS时间超过100ms
                dns_slow_entries.append({
                    "url": entry.get("request", {}).get("url", ""),
                    "dns_time": dns_time
                })
        
        if dns_slow_entries:
            bottlenecks.append({
                "type": "dns_slow",
                "description": "DNS解析时间过长",
                "entries": dns_slow_entries[:5]  # 只显示前5个
            })
        
        # 连接时间过长
        connect_slow_entries = []
        for entry in entries:
            timings = entry.get("timings", {})
            connect_time = timings.get("connect", -1)
            if connect_time > 200:  # 连接时间超过200ms
                connect_slow_entries.append({
                    "url": entry.get("request", {}).get("url", ""),
                    "connect_time": connect_time
                })
        
        if connect_slow_entries:
            bottlenecks.append({
                "type": "connect_slow",
                "description": "TCP连接时间过长",
                "entries": connect_slow_entries[:5]
            })
        
        # 等待时间过长（服务器响应慢）
        wait_slow_entries = []
        for entry in entries:
            timings = entry.get("timings", {})
            wait_time = timings.get("wait", -1)
            if wait_time > 500:  # 等待时间超过500ms
                wait_slow_entries.append({
                    "url": entry.get("request", {}).get("url", ""),
                    "wait_time": wait_time
                })
        
        if wait_slow_entries:
            bottlenecks.append({
                "type": "wait_slow",
                "description": "服务器响应时间过长",
                "entries": wait_slow_entries[:5]
            })
        
        # 生成建议
        recommendations = []
        
        if dns_slow_entries:
            recommendations.append("优化DNS解析：考虑使用更快的DNS服务器或DNS预解析")
        
        if connect_slow_entries:
            recommendations.append("优化TCP连接：启用HTTP/2、减少域名分片、使用连接复用")
        
        if wait_slow_entries:
            recommendations.append("优化服务器响应：启用缓存、压缩资源、优化后端代码")
        
        # 检查资源大小
        large_resources = []
        for entry in entries:
            response = entry.get("response", {})
            content = response.get("content", {})
            size = content.get("size", 0)
            mime_type = content.get("mimeType", "")
            
            if size > 1024 * 1024:  # 大于1MB
                large_resources.append({
                    "url": entry.get("request", {}).get("url", ""),
                    "size": size,
                    "type": mime_type
                })
        
        if large_resources:
            bottlenecks.append({
                "type": "large_resources",
                "description": "资源文件过大",
                "entries": large_resources[:5]
            })
            recommendations.append("压缩大资源：使用图片压缩、代码压缩、懒加载等技术")
        
        return {
            "status": "success",
            "data": {
                "summary": {
                    "total_requests": request_count,
                    "total_time_ms": total_time,
                    "total_size_bytes": total_size,
                    "average_time_per_request": total_time / request_count if request_count > 0 else 0,
                    "average_size_per_request": total_size / request_count if request_count > 0 else 0
                },
                "slowest_resource": {
                    "url": slowest_entry.get("request", {}).get("url", "") if slowest_entry else None,
                    "time_ms": max_time,
                    "type": slowest_entry.get("response", {}).get("content", {}).get("mimeType", "") if slowest_entry else None
                },
                "resource_types": resource_types,
                "bottlenecks": bottlenecks,
                "recommendations": recommendations
            },
            "error": None
        }
    
    async def compare_har_files(self, har1_path: str, har2_path: str) -> Dict[str, Any]:
        """比较两个HAR文件"""
        try:
            # 读取HAR文件
            with open(har1_path, 'r', encoding='utf-8') as f:
                har1 = json.load(f)
            
            with open(har2_path, 'r', encoding='utf-8') as f:
                har2 = json.load(f)
            
            # 分析差异
            entries1 = har1.get("log", {}).get("entries", [])
            entries2 = har2.get("log", {}).get("entries", [])
            
            # 计算总时间
            total_time1 = sum(entry.get("time", 0) for entry in entries1)
            total_time2 = sum(entry.get("time", 0) for entry in entries2)
            
            # 计算总大小
            total_size1 = sum(entry.get("response", {}).get("content", {}).get("size", 0) for entry in entries1)
            total_size2 = sum(entry.get("response", {}).get("content", {}).get("size", 0) for entry in entries2)
            
            diff = {
                "request_count_diff": len(entries2) - len(entries1),
                "total_time_diff": total_time2 - total_time1,
                "total_size_diff": total_size2 - total_size1,
                "improvements": [],
                "regressions": []
            }
            
            # 分析性能变化
            if total_time2 > total_time1 * 1.2:  # 时间增加超过20%
                diff["regressions"].append({
                    "type": "performance",
                    "description": f"总加载时间增加: {total_time1:.0f}ms → {total_time2:.0f}ms (+{((total_time2/total_time1)-1)*100:.1f}%)"
                })
            elif total_time2 < total_time1 * 0.8:  # 时间减少超过20%
                diff["improvements"].append({
                    "type": "performance",
                    "description": f"总加载时间减少: {total_time1:.0f}ms → {total_time2:.0f}ms (-{((1-total_time2/total_time1))*100:.1f}%)"
                })
            
            # 分析请求数量变化
            if len(entries2) > len(entries1) * 1.5:  # 请求数增加超过50%
                diff["regressions"].append({
                    "type": "requests",
                    "description": f"请求数量大幅增加: {len(entries1)} → {len(entries2)} (+{((len(entries2)/len(entries1))-1)*100:.1f}%)"
                })
            elif len(entries2) < len(entries1) * 0.7:  # 请求数减少超过30%
                diff["improvements"].append({
                    "type": "requests",
                    "description": f"请求数量减少: {len(entries1)} → {len(entries2)} (-{((1-len(entries2)/len(entries1)))*100:.1f}%)"
                })
            
            return {
                "status": "success",
                "data": diff,
                "error": None
            }
            
        except FileNotFoundError as e:
            return {
                "status": "error",
                "data": None,
                "error": f"文件未找到: {str(e)}"
            }
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "data": None,
                "error": f"JSON解析错误: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "error": f"比较失败: {str(e)}"
            }
