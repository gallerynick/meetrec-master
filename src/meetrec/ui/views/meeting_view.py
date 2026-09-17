"""会议详情视图：5 步流程条 + 步骤内容占位。

对应 docs/09 §4.1。M1 骨架：流程条可用，步骤内容为占位说明。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from meetrec.ui.flow_bar import STEP_TITLES, FlowBar
from meetrec.ui.theme import SIZING

__all__ = ["MeetingView"]

_STEP_DESCRIPTIONS: tuple[str, ...] = (
    "录音按钮、实时电平表、音频导入拖拽区（M2 交付）。",
    "faster-whisper 四阶段转写 + 热词定向重解码（M3 交付）。",
    "热词高亮与人工校正，9 道闸门防误改（M3 交付）。",
    "多 AI 提供方纪要生成（M5 交付）。",
    "导出 Markdown / PDF / Word（M6 交付）。",
)


class MeetingView(QFrame):
    """会议详情视图。"""

    step_content_changed = Signal(int)

    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")

        root = QVBoxLayout(self)
        root.setContentsMargins(
            SIZING.space_2xl, SIZING.space_lg, SIZING.space_2xl, SIZING.space_lg
        )
        root.setSpacing(SIZING.space_lg)

        title = QLabel("会议详情")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        self._flow = FlowBar()
        self._flow.step_selected.connect(self._on_step_selected)
        root.addWidget(self._flow)

        self._stack = QStackedWidget()
        for i, name in enumerate(STEP_TITLES):
            self._stack.addWidget(self._build_step(i + 1, name))
        root.addWidget(self._stack, 1)

    def _build_step(self, index: int, title: str) -> QWidget:
        """单个步骤的占位内容。"""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(SIZING.space_xl, SIZING.space_xl, SIZING.space_xl, SIZING.space_xl)
        lay.setSpacing(SIZING.space_md)
        lay.addStretch()

        heading = QLabel(f"步骤 {index} · {title}")
        heading.setObjectName("EmptyTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(heading)

        desc = QLabel(_STEP_DESCRIPTIONS[index - 1])
        desc.setObjectName("EmptySubtitle")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addStretch()
        return box

    def _on_step_selected(self, index: int) -> None:
        self._stack.setCurrentIndex(index - 1)
        self.step_content_changed.emit(index)

    def flow_bar(self) -> FlowBar:
        """返回流程条（供测试与后续逻辑使用）。"""
        return self._flow
