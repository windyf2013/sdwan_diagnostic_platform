"""
CLI 输出格式化工具
"""

from typing import List, Optional
from sdwan_desktop.core.types.diagnosis import DiagnosisResult, RootCause, Recommendation, Severity


def colorize(text: str, severity: Optional[Severity] = None) -> str:
    """根据严重程度为文本添加颜色 ANSI 代码
    
    Args:
        text: 原始文本
        severity: 严重程度
        
    Returns:
        带颜色的文本字符串
    """
    if not severity:
        return text
        
    colors = {
        Severity.CRITICAL: "\033[91m",  # Red
        Severity.ERROR: "\033[91m",      # Red
        Severity.WARNING: "\033[93m",    # Yellow
        Severity.INFO: "\033[92m",       # Green
    }
    reset = "\033[0m"
    
    color_code = colors.get(severity, "")
    return f"{color_code}{text}{reset}"


def format_severity_badge(severity: Severity) -> str:
    """格式化严重程度徽章
    
    Args:
        severity: 严重程度
        
    Returns:
        徽章字符串
    """
    icons = {
        Severity.CRITICAL: "🔴 严重",
        Severity.ERROR: "🟠 错误",
        Severity.WARNING: "⚠️ 警告",
        Severity.INFO: "ℹ️ 信息",
    }
    return icons.get(severity, "❓ 未知")


def format_diagnosis_summary(result: DiagnosisResult) -> str:
    """格式化诊断摘要
    
    Args:
        result: 诊断结果
        
    Returns:
        格式化后的摘要字符串
    """
    lines = []
    lines.append("=" * 60)
    lines.append("📋 诊断结果摘要")
    lines.append("=" * 60)
    
    # 确定整体严重程度
    max_severity = Severity.INFO
    if result.root_causes:
        severities = [rc.severity for rc in result.root_causes]
        if Severity.CRITICAL in severities:
            max_severity = Severity.CRITICAL
        elif Severity.ERROR in severities:
            max_severity = Severity.ERROR
        elif Severity.WARNING in severities:
            max_severity = Severity.WARNING
            
    lines.append(f"严重程度: {format_severity_badge(max_severity)}")
    lines.append(f"综合置信度: {int(result.overall_confidence * 100)}%")
    lines.append("")
    
    if result.root_causes:
        lines.append(f"🔴 发现 {len(result.root_causes)} 个问题:")
        lines.append("")
        for i, cause in enumerate(result.root_causes, 1):
            lines.append(f"{i}. [{cause.cause_id}] {cause.title} (置信度: {int(cause.confidence * 100)}%)")
            lines.append(f"   {cause.description}")
            lines.append("")
    else:
        lines.append("✅ 未发现明显网络配置问题。")
        lines.append("")
        
    return "\n".join(lines)


def format_root_causes(causes: List[RootCause]) -> str:
    """格式化根因列表
    
    Args:
        causes: 根因列表
        
    Returns:
        格式化后的字符串
    """
    if not causes:
        return "无根因分析结果。"
        
    lines = []
    lines.append("🔍 根因分析详情:")
    lines.append("-" * 40)
    
    for cause in causes:
        lines.append(f"ID: {cause.cause_id}")
        lines.append(f"标题: {cause.title}")
        lines.append(f"描述: {cause.description}")
        lines.append(f"严重程度: {cause.severity.value}")
        lines.append(f"置信度: {cause.confidence}")
        if cause.evidence_refs:
            lines.append(f"证据引用: {', '.join(cause.evidence_refs)}")
        lines.append("")
        
    return "\n".join(lines)


def format_recommendations(recs: List[Recommendation]) -> str:
    """格式化建议列表
    
    Args:
        recs: 建议列表
        
    Returns:
        格式化后的字符串
    """
    if not recs:
        return ""
        
    lines = []
    lines.append("💡 诊断建议:")
    
    # 按优先级排序
    sorted_recs = sorted(recs, key=lambda x: x.priority)
    
    for i, rec in enumerate(sorted_recs, 1):
        lines.append(f"   {i}. [优先级 {rec.priority}] {rec.action}")
        if rec.expected_outcome:
            lines.append(f"      预期结果: {rec.expected_outcome}")
            
    lines.append("")
    return "\n".join(lines)