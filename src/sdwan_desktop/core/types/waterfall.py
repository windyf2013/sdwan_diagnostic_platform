"""
Waterfall数据契约 - 定义资源时序和瀑布流结果

遵循 SDWAN_SPEC.md §2.1 数据结构规范
使用 dataclass(slots=True) 装饰器
"""

from dataclasses import dataclass, field
from typing import List, Optional
import uuid
from datetime import datetime, timezone


@dataclass(slots=True)
class ResourceTiming:
    """资源加载时序信息
    
    对应 HAR 中的 entry.timings 字段，记录各阶段耗时。
    """
    
    # 业务字段：无默认值的放在最前
    url: str
    """资源URL"""
    
    # 基础字段（有默认值）
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # 业务字段：有默认值的
    method: str = "GET"
    """HTTP方法"""
    
    status_code: int = 0
    """HTTP状态码"""
    
    # 各阶段耗时 (毫秒)
    dns_time: float = 0.0
    """DNS解析耗时"""
    
    connect_time: float = 0.0
    """TCP连接建立耗时"""
    
    ssl_time: float = 0.0
    """SSL/TLS握手耗时"""
    
    wait_time: float = 0.0
    """等待服务器响应耗时 (TTFB)"""
    
    download_time: float = 0.0
    """内容下载耗时"""
    
    total_time: float = 0.0
    """总耗时"""
    
    content_size: int = 0
    """内容大小 (字节)"""
    
    mime_type: str = ""
    """MIME类型"""
    
    is_render_blocking: bool = False
    """是否阻塞渲染 (如CSS/JS)"""


@dataclass(slots=True)
class WaterfallResult:
    """瀑布流分析结果
    
    聚合所有资源的时序信息及整体页面性能指标。
    """
    
    # 业务字段：无默认值的放在最前
    target_url: str
    """目标页面URL"""
    
    # 基础字段（有默认值）
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    resources: List[ResourceTiming] = field(default_factory=list)
    """所有资源的时序列表"""
    
    # 总体指标
    page_load_time: float = 0.0
    """页面完全加载耗时 (ms)"""
    
    dom_content_loaded: float = 0.0
    """DOM内容加载完成耗时 (ms)"""
    
    total_requests: int = 0
    """总请求数"""
    
    total_size_bytes: int = 0
    """总传输大小 (字节)"""
    
    slowest_resources: List[ResourceTiming] = field(default_factory=list)
    """最慢的5个资源"""
    
    render_blocking_count: int = 0
    """阻塞渲染的资源数量"""
    
    def calculate_stats(self) -> None:
        """计算统计信息"""
        self.total_requests = len(self.resources)
        self.total_size_bytes = sum(r.content_size for r in self.resources)
        self.render_blocking_count = sum(1 for r in self.resources if r.is_render_blocking)
        
        # 按总耗时排序，取最慢的5个
        sorted_resources = sorted(self.resources, key=lambda x: x.total_time, reverse=True)
        self.slowest_resources = sorted_resources[:5]
        
        # 简单估算页面加载时间（取最大结束时间）
        if self.resources:
            self.page_load_time = max(r.total_time for r in self.resources)
