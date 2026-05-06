"""
HAR解析服务 - 将HAR文件解析为WaterfallResult

遵循 SDWAN_SPEC.md §2.2.3 函数分类标准 (service_function)
"""

import json
import logging
from typing import Any, Dict, List

from sdwan_desktop.core.types.waterfall import ResourceTiming, WaterfallResult
from sdwan_desktop.tools.registry.decorator import service_function

logger = logging.getLogger(__name__)


class HarParser:
    """HAR文件解析器
    
    解析HAR JSON结构，提取资源时序并计算性能指标。
    """

    @service_function
    def parse(self, har_file_path: str, trace_id: str = "") -> WaterfallResult:
        """解析HAR文件
        
        Args:
            har_file_path: HAR文件路径
            trace_id: 追踪ID
            
        Returns:
            WaterfallResult: 解析后的瀑布流结果
        """
        try:
            with open(har_file_path, 'r', encoding='utf-8') as f:
                har_data = json.load(f)
            
            log = har_data.get("log", {})
            entries = log.get("entries", [])
            
            resources = []
            for entry in entries:
                resource = self._parse_entry(entry)
                if resource:
                    resources.append(resource)
            
            result = WaterfallResult(
                target_url=log.get("pages", [{}])[0].get("startedDateTime", ""),
                resources=resources,
                trace_id=trace_id
            )
            
            result.calculate_stats()
            return result

        except Exception as e:
            logger.error(f"Failed to parse HAR file {har_file_path}: {str(e)}")
            raise

    def _parse_entry(self, entry: Dict[str, Any]) -> ResourceTiming:
        """解析单个HAR条目
        
        Args:
            entry: HAR条目字典
            
        Returns:
            ResourceTiming: 资源时序对象
        """
        request = entry.get("request", {})
        response = entry.get("response", {})
        timings = entry.get("timings", {})
        
        # 提取URL和方法
        url = request.get("url", "")
        method = request.get("method", "GET")
        
        # 提取状态码和内容大小
        status_code = response.get("status", 0)
        content_size = response.get("bodySize", 0)
        mime_type = response.get("content", {}).get("mimeType", "")
        
        # 提取各阶段耗时 (单位通常是ms，但HAR中可能是负数表示并行)
        dns_time = max(timings.get("dns", 0), 0)
        connect_time = max(timings.get("connect", 0), 0)
        ssl_time = max(timings.get("ssl", -1), 0)  # -1表示未使用SSL
        wait_time = max(timings.get("wait", 0), 0)
        download_time = max(timings.get("receive", 0), 0)
        
        total_time = sum([dns_time, connect_time, ssl_time, wait_time, download_time])
        
        # 简单的渲染阻塞判断：CSS和JS通常阻塞渲染
        is_render_blocking = mime_type in ["text/css", "application/javascript", "text/javascript"]
        
        return ResourceTiming(
            url=url,
            method=method,
            status_code=status_code,
            dns_time=dns_time,
            connect_time=connect_time,
            ssl_time=ssl_time,
            wait_time=wait_time,
            download_time=download_time,
            total_time=total_time,
            content_size=content_size,
            mime_type=mime_type,
            is_render_blocking=is_render_blocking
        )
