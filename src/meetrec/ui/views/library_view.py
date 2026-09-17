"""会议库视图。

对应 docs/09 §7.4 空态：会议库为空时显示引导文案 + 「新建会议」主按钮。
M1 骨架：演示空态与占位列表的切换。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from meetrec.ui.theme import SIZING

__all__ = ["LibraryView"]


class LibraryView(QFrame):
    """会议库视图：列表 + 空态引导。"""

    new_meeting_requested = Signal()
    meeting_selected = Signal(str)

    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")
        self._stack = QStackedWidget()
        self._empty: QWidget
        self._list: QWidget
        self._build()
        self.set_has_meetings(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(
            SIZING.space_2xl, SIZING.space_2xl, SIZING.space_2xl, SIZING.space_2xl
        )
        root.setSpacing(SIZING.space_md)

        title = QLabel("会议库")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        root.addWidget(self._stack, 1)

    def _build(self) -> None:
        self._empty = self._build_empty()
        self._list = self._build_list()
        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._list)

    def _build_empty(self) -> QWidget:
        """空态：引导文案 + 新建会议主按钮。"""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SIZING.space_md)
        lay.addStretch()

        title = QLabel("还没有会议")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        subtitle = QLabel("导入音频或开始录音，生成第一份会议纪要。")
        subtitle.setObjectName("EmptySubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        lay.addSpacing(SIZING.space_lg)
        btn = QPushButton("+ 新建会议")
        btn.setObjectName("Primary")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.new_meeting_requested)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)

        lay.addStretch()
        return box

    def _build_list(self) -> QWidget:
        """占位列表：两个演示会议项（M2 替换为真实存储）。"""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SIZING.space_sm)

        for name, date in (("产品评审会", "2026-01-15"), ("需求讨论", "2026-01-14")):
            row = QFrame()
            row.setObjectName("NavItem")
            row.setStyleSheet("border-radius: 8px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(
                SIZING.space_md, SIZING.space_sm, SIZING.space_md, SIZING.space_sm
            )
            rl.addWidget(QLabel(f"●  {name}"))
            rl.addStretch()
            date_lbl = QLabel(date)
            date_lbl.setObjectName("Caption")
            rl.addWidget(date_lbl)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            lay.addWidget(row)

        lay.addStretch()
        return box

    def set_has_meetings(self, has: bool) -> None:
        """切换空态 / 列表态。"""
        self._stack.setCurrentWidget(self._list if has else self._empty)
