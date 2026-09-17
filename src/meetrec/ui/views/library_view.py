"""会议库视图。

对应 docs/09 §7.4 空态：会议库为空时显示引导文案 + 「新建会议」主按钮。
M2–M6 后接真实 MeetingStore 数据。
"""

from __future__ import annotations

from functools import partial

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

from meetrec.models import Meeting
from meetrec.ui.service import MeetingService
from meetrec.ui.theme import SIZING

__all__ = ["LibraryView"]


class LibraryView(QFrame):
    """会议库视图：列表 + 空态引导。"""

    new_meeting_requested = Signal()
    meeting_selected = Signal(str)

    def __init__(self, service: MeetingService, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.setObjectName("Content")
        self._stack = QStackedWidget()
        self._empty: QWidget
        self._list: QWidget
        self._build()
        self._refresh()

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
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SIZING.space_sm)
        self._list_layout = lay
        lay.addStretch()
        return box

    def _refresh(self) -> None:
        meetings = self._service.list_meetings()
        has = len(meetings) > 0
        self._stack.setCurrentWidget(self._list if has else self._empty)

        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for meeting in sorted(meetings, key=lambda m: m.created_at, reverse=True):
            self._add_meeting_row(meeting)

    def _add_meeting_row(self, meeting: Meeting) -> None:
        row = QFrame()
        row.setObjectName("NavItem")
        row.setStyleSheet("border-radius: 8px;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(
            SIZING.space_md, SIZING.space_sm, SIZING.space_md, SIZING.space_sm
        )

        status_icon = "●"
        if meeting.has_summary():
            status_icon = "✓"
        elif meeting.has_transcript():
            status_icon = "◐"
        elif meeting.has_audio():
            status_icon = "◌"

        rl.addWidget(QLabel(f"{status_icon}  {meeting.display_title}"))
        rl.addStretch()
        date_lbl = QLabel(meeting.created_at[:10])
        date_lbl.setObjectName("Caption")
        rl.addWidget(date_lbl)

        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.mousePressEvent = partial(self._on_row_clicked, meeting.id)
        self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _on_row_clicked(self, meeting_id: str) -> None:
        self.meeting_selected.emit(meeting_id)

    def refresh(self) -> None:
        self._refresh()
