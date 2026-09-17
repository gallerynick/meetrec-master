"""单实例锁。

使用 Qt 的 QLockFile 保证同一用户同一时间只运行一个 MeetRec Master 实例。
锁文件位于应用数据目录（与 ADR-007 同一存储布局）。
"""

from __future__ import annotations

from PySide6.QtCore import QLockFile

from meetrec.errors import MeetRecError
from meetrec.paths import data_dir

__all__ = ["SingleInstanceError", "SingleInstanceGuard"]


class SingleInstanceError(MeetRecError):
    """已有 MeetRec Master 实例在运行。"""


class SingleInstanceGuard:
    """单实例守卫。

    用法::

        guard = SingleInstanceGuard()
        if not guard.try_acquire():
            raise SingleInstanceError(message="MeetRec Master 已在运行")
        try:
            ...  # 运行应用
        finally:
            guard.release()
    """

    def __init__(self, lock_path: str | None = None) -> None:
        path = lock_path or str(data_dir() / "meetrec.lock")
        self._path = path
        self._file = QLockFile(path)
        self._acquired = False

    @property
    def lock_path(self) -> str:
        """锁文件路径。"""
        return self._path

    def try_acquire(self) -> bool:
        """尝试获取锁。成功返回 True，已有实例持锁返回 False。"""
        self._acquired = self._file.tryLock(0)
        return self._acquired

    def release(self) -> None:
        """释放锁。幂等。"""
        if self._acquired:
            self._file.unlock()
            self._acquired = False

    def __enter__(self) -> SingleInstanceGuard:
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
