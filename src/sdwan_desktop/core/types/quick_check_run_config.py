"""CLI/GUI 一键体检运行边界配置（pydantic 校验）。"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class QuickCheckRunConfig(BaseModel):
    """一键体检入口参数：在 Interface 层校验后再进入 Flow。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    output_format: Literal["html", "json"] = "html"
    report_output: Optional[str] = Field(
        default=None,
        description="报告路径；None 表示写入默认 reports 目录",
    )
