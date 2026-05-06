"""
报告生成器模块

负责生成诊断报告，支持多种输出格式
"""

from .report_generator import ReportGenerator, ReportFormat, ReportSection

__all__ = [
    "ReportGenerator",
    "ReportFormat",
    "ReportSection",
]
