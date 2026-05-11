"""
报告生成器

生成诊断报告，支持文本、JSON和HTML格式
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from sdwan_desktop.core.types.context import FlowContext
from sdwan_desktop.services.orchestrator.diagnostic_flow import DiagnosticResult
from sdwan_desktop.services.analyzer.rule_engine import RuleResult, Severity
from sdwan_desktop.core.types.waterfall import WaterfallResult

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """报告格式"""
    TEXT = "text"
    """纯文本"""
    JSON = "json"
    """JSON"""
    MARKDOWN = "``"
    """``"""
    HTML = "html"
    """HTML"""


@dataclass
class ReportSection:
    """报告章节"""
    title: str
    """标题"""
    content: str
    """内容"""
    level: int = 1
    """标题级别"""
    subsections: List["ReportSection"] = field(default_factory=list)
    """子章节"""


class ReportGenerator:
    """报告生成器
    
    将诊断结果转换为可读的报告
    支持文本、JSON、Markdown和HTML格式
    """
    
    def __init__(self, format: ReportFormat = ReportFormat.TEXT):
        """初始化报告生成器
        
        Args:
            format: 输出格式
        """
        self.format = format
        # 初始化 Jinja2 环境
        template_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reporting", "templates")
        self.env = Environment(loader=FileSystemLoader(template_dir))
        
        # 注册自定义过滤器：为URL生成唯一ID（使用hash）
        def url_hash_filter(url):
            """为URL生成唯一的hash ID"""
            import hashlib
            # 使用MD5生成短hash（前8位）
            hash_value = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
            return hash_value
        
        self.env.filters['hash'] = url_hash_filter

    def generate_waterfall_report(self, waterfall: WaterfallResult, issues: List[Dict], output_path: str = None) -> str:
        """生成 Waterfall HTML 报告
        
        Args:
            waterfall: 瀑布流数据
            issues: 性能诊断问题列表
            output_path: 输出文件路径（可选）
            
        Returns:
            str: HTML 内容
        """
        template = self.env.get_template("waterfall.html")
        
        context = {
            "target_url": waterfall.target_url,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "page_load_time": round(waterfall.page_load_time, 2),
            "total_requests": waterfall.total_requests,
            "total_size_kb": round(waterfall.total_size_bytes / 1024, 2),
            "render_blocking_count": waterfall.render_blocking_count,
            "resources": [{"index": i, **asdict(r)} for i, r in enumerate(waterfall.resources)],
            "issues": issues
        }
        
        html_content = template.render(**context)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"Waterfall report saved to {output_path}")
            
        return html_content