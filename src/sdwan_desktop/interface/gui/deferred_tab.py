"""延迟实例化标签页：首次切换到该页时才加载重型模块。"""

from __future__ import annotations

from typing import Callable, Optional, TypeVar

from PySide6.QtWidgets import QVBoxLayout, QWidget

T = TypeVar("T", bound=QWidget)


class DeferredTabHost(QWidget):
    """占位容器；``ensure_loaded`` 后挂载真实标签页 widget。"""

    def __init__(
        self,
        factory: Callable[[], T],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._factory = factory
        self._inner: Optional[T] = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QWidget(self)
        self._layout.addWidget(self._placeholder)

    def ensure_loaded(self) -> T:
        if self._inner is not None:
            return self._inner
        self._layout.removeWidget(self._placeholder)
        self._placeholder.deleteLater()
        self._inner = self._factory()
        self._layout.addWidget(self._inner)
        return self._inner

    def inner(self) -> Optional[T]:
        return self._inner
