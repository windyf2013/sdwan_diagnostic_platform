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
            
            logger.info(f"开始解析HAR文件: {har_file_path}, 共 {len(entries)} 个条目")
            
            resources = []
            domain_stats = {}  # 统计每个域名的请求数
            
            for i, entry in enumerate(entries):
                resource = self._parse_entry(entry)
                if resource:
                    resources.append(resource)
                    
                    # 统计域名
                    from urllib.parse import urlparse
                    try:
                        parsed = urlparse(resource.url)
                        domain = parsed.netloc
                        domain_stats[domain] = domain_stats.get(domain, 0) + 1
                    except:
                        pass
                    
                    # 记录前5个和后5个资源的详细信息
                    if i < 5 or i >= len(entries) - 5:
                        logger.debug(f"  [{i+1}/{len(entries)}] {resource.method} {resource.url[:80]} - {resource.total_time}ms")
            
            # 输出域名统计
            logger.info(f"解析完成，共 {len(resources)} 个资源")
            logger.info("域名分布:")
            for domain, count in sorted(domain_stats.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {domain}: {count} 个请求")
            
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
            ResourceTiming: 资源时序对象，如果完全无效则返回None
        """
        request = entry.get("request", {})
        response = entry.get("response", {})
        timings = entry.get("timings", {})
        
        # 提取URL和方法
        url = request.get("url", "")
        method = request.get("method", "GET")
        
        # 如果没有URL，跳过此条目
        if not url:
            logger.debug(f"Skipping entry with no URL")
            return None
        
        # 提取状态码和内容大小
        status_code = response.get("status", 0)
        content_size = response.get("bodySize", 0)
        mime_type = response.get("content", {}).get("mimeType", "")
        
        # 提取各阶段耗时 (单位通常是ms，但HAR中可能是负数表示并行)
        dns_time = max(timings.get("dns", -1), 0)  # -1表示未执行DNS
        connect_time = max(timings.get("connect", -1), 0)  # -1表示未执行连接
        ssl_time = max(timings.get("ssl", -1), 0)  # -1表示未使用SSL
        wait_time = max(timings.get("wait", -1), 0)  # -1表示未完成
        download_time = max(timings.get("receive", -1), 0)  # -1表示未完成
        
        # 检查是否有blocked时间（请求被阻塞的时间）
        blocked_time = max(timings.get("blocked", 0), 0)
        
        # 计算总耗时
        total_time = sum([dns_time, connect_time, ssl_time, wait_time, download_time])
        
        # 处理特殊情况：所有阶段都为0或-1
        if total_time == 0:
            # 情况1: 有blocked时间，说明请求被调度阻塞了
            if blocked_time > 0:
                wait_time = blocked_time
                total_time = blocked_time
                logger.debug(f"Resource with only blocked time: {url[:80]}... ({blocked_time}ms)")
            
            # 情况2: 尝试使用HAR的time字段
            else:
                har_time = entry.get("time", -1)
                if har_time > 0:
                    total_time = har_time
                    # 将总耗时分配给wait_time（等待服务器响应的时间）
                    if wait_time == 0:
                        wait_time = har_time
                    logger.debug(f"Using HAR time field: {url[:80]}... ({har_time}ms)")
                
                # 情况3: 请求被取消或失败，没有时序数据
                elif status_code == -1 or status_code == 0:
                    # 即使是失败的请求，也应该显示在瀑布流图中
                    # 使用HAR的time字段（如果有），否则设置最小值
                    har_time = entry.get("time", -1)
                    if har_time > 0:
                        total_time = har_time
                        wait_time = har_time
                        logger.debug(f"Failed request using HAR time: {url[:80]}... (time={har_time}ms, status={status_code})")
                    else:
                        # 没有time字段，设置一个合理的最小值确保可见
                        wait_time = 1.0  # 1ms表示失败的请求
                        total_time = 1.0
                        logger.warning(f"Failed request with no timing data: {url[:80]}... (status={status_code}, using 1ms)")
                
                # 情况4: 其他失败情况（HTTP错误码），设置最小值
                elif status_code >= 400:
                    har_time = entry.get("time", -1)
                    if har_time > 0:
                        total_time = har_time
                        wait_time = har_time
                    else:
                        wait_time = 1.0
                        total_time = 1.0
                    logger.debug(f"HTTP error request: {url[:80]}... (status={status_code}, time={total_time}ms)")

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
