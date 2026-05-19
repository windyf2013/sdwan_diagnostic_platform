"""报告用户可见文案清洗（去除调试字段，保留 JSON 中的 trace_id）。"""

from __future__ import annotations

import re
from typing import List, Optional

from sdwan_desktop.core.types.diagnosis import RootCause

# 工具层错误常附带 ``(trace_id: uuid)``，不应出现在 HTML 结论/根因卡片。
_TRACE_ID_PAREN = re.compile(r"\s*\(trace_id:\s*[0-9a-fA-F-]{8,}\)\s*", re.IGNORECASE)
_TRACE_ID_TRAILING = re.compile(r"\s*trace_id:\s*[0-9a-fA-F-]{8,}\s*$", re.IGNORECASE)


def sanitize_user_visible_text(text: Optional[str]) -> str:
    """移除用户可见字符串中的 trace_id 后缀/括号段。"""
    if not text:
        return ""
    out = _TRACE_ID_PAREN.sub(" ", str(text))
    out = _TRACE_ID_TRAILING.sub("", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def sanitize_root_causes_for_display(causes: List[RootCause]) -> List[RootCause]:
    """就地清洗根因标题与描述中的 trace_id（不改变 cause_id 等结构字段）。"""
    for c in causes:
        c.title = sanitize_user_visible_text(c.title)
        c.description = sanitize_user_visible_text(c.description)
    return causes
