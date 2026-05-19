"""诊断 Tab 共用布局：顶部说明 + 可滚动表单（板块按内容高度，不纵向拉伸）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_SCOPE_MAX_HEIGHT = 44
_FORM_ROW_HEIGHT = 28


def make_tab_scope_label(text: str) -> QLabel:
    """页顶功能说明：固定最多两行高度，不参与纵向比例拉伸。"""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setMaximumHeight(_SCOPE_MAX_HEIGHT)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
    return label


def compact_form_field(widget: QWidget) -> None:
    """表单控件统一行高，避免被布局纵向拉高。"""
    widget.setMinimumHeight(_FORM_ROW_HEIGHT)
    widget.setMaximumHeight(_FORM_ROW_HEIGHT)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


def add_diagnosis_group(form_inner: QVBoxLayout, group: QGroupBox) -> None:
    """加入分组框：仅占内容高度，宽度随窗口伸展。"""
    group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
    form_inner.addWidget(group, 0, Qt.AlignmentFlag.AlignTop)


def finalize_diagnosis_form(form_inner: QVBoxLayout) -> None:
    """表单末尾弹性空白，避免各 GroupBox 按窗口高度比例被拉高。"""
    form_inner.addStretch(1)


def diagnosis_tab_layout(
    host: QWidget,
    scope_text: str,
) -> tuple[QVBoxLayout, QVBoxLayout, QLabel]:
    """构建诊断页：说明 + 可滚动表单 + 底栏状态。

    Returns:
        ``(root, form_inner, status_label)``
    """
    root = QVBoxLayout(host)
    root.setContentsMargins(8, 6, 8, 6)
    root.setSpacing(6)

    root.addWidget(make_tab_scope_label(scope_text), 0, Qt.AlignmentFlag.AlignTop)

    form_host = QWidget()
    form_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    form_inner = QVBoxLayout(form_host)
    form_inner.setContentsMargins(0, 0, 0, 0)
    form_inner.setSpacing(8)
    form_inner.setAlignment(Qt.AlignmentFlag.AlignTop)
    form_inner.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setWidget(form_host)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    root.addWidget(scroll, 1)

    status = QLabel("就绪")
    status.setFixedHeight(22)
    status.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    status.setWordWrap(False)

    return root, form_inner, status


def set_compact_status(label: QLabel, text: str, *, max_len: int = 140) -> None:
    """状态行仅显示单行摘要；完整内容放入 tooltip（供复制）。"""
    raw = (text or "").strip()
    one_line = " ".join(raw.splitlines())
    if len(one_line) > max_len:
        label.setText(one_line[: max_len - 1] + "…")
        label.setToolTip(raw)
    else:
        label.setText(one_line or "就绪")
        label.setToolTip(raw if raw and raw != label.text() else "")
