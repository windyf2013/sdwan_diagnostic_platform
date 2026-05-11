"""
性能分析服务 - 识别Web性能瓶颈

遵循 SDWAN_SPEC.md §2.2.3 函数分类标准 (service_function)
"""

import logging
from typing import List

from sdwan_desktop.core.types.waterfall import WaterfallResult, ResourceTiming
from sdwan_desktop.tools.registry.decorator import service_function

logger = logging.getLogger(__name__)


class PerfAnalyzer:
    """性能分析器
    
    基于 WaterfallResult 进行深度分析，识别最慢资源及渲染阻塞项。
    """

    @service_function
    def analyze(self, waterfall: WaterfallResult) -> dict:
        """执行性能分析
        
        Args:
            waterfall: 瀑布流解析结果
            
        Returns:
            dict: 包含分析摘要和建议的字典
        """
        if not waterfall:
            return {"error": "Waterfall result is empty"}

        # 1. 识别最慢资源（已在 calculate_stats 中排序）
        slowest = waterfall.slowest_resources[:5]
        
        # 2. 识别渲染阻塞资源
        blocking = [r for r in waterfall.resources if r.is_render_blocking]
        
        summary = {
            "total_requests": waterfall.total_requests,
            "total_size_kb": round(waterfall.total_size_bytes / 1024, 2),
            "page_load_time_ms": round(waterfall.page_load_time, 2),
            "slowest_resources": [self._resource_to_dict(r) for r in slowest],
            "render_blocking_count": len(blocking),
            "render_blocking_urls": [r.url for r in blocking],
        }

        logger.info(f"Performance analysis completed for {waterfall.target_url}. Load time: {waterfall.page_load_time}ms")
        return summary

    def _resource_to_dict(self, resource: ResourceTiming) -> dict:
        """将资源对象转换为字典以便报告展示"""
        return {
            "url": resource.url,
            "total_time_ms": round(resource.total_time, 2),
            "dns_ms": round(resource.dns_time, 2),
            "connect_ms": round(resource.connect_time, 2),
            "ssl_ms": round(resource.ssl_time, 2),
            "wait_ms": round(resource.wait_time, 2),
            "download_ms": round(resource.download_time, 2),
            "size_bytes": resource.content_size,
        }
