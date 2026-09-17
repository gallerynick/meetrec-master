"""后台线程 Worker。

将长耗时操作（转写、纪要生成）放到 QThread 中执行，避免阻塞 UI 线程。
如果调用函数接受 progress_cb 参数，自动注入 Signal 发射器。
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal

__all__ = ["Worker"]


class Worker(QThread):
    """通用后台 Worker。"""

    progress = Signal(str)
    result_ready = Signal(object)
    error = Signal(str)

    def __init__(self, fn: Callable, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            kwargs = dict(self._kwargs)
            sig = inspect.signature(self._fn)
            if "progress_cb" in sig.parameters:
                kwargs["progress_cb"] = lambda msg: self.progress.emit(msg)
            result = self._fn(*self._args, **kwargs)
            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")
