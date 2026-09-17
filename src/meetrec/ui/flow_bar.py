"""5 步流程条。

对应 docs/09 §4.1：录音/导入 → 转写 → 关键词校对 → 生成纪要 → 导出。
状态视觉：
- 待开始：透明底 + border 描边 + text-tertiary
- 进行中：accent 实心 + 白字
- 已完成：success 实心 + 白字
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from meetrec.ui.theme import SIZING

__all__ = ["STEP_TITLES", "FlowBar", "Step", "StepState"]

STEP_TITLES: tuple[str, ...] = ("录音/导入", "转写", "关键词校对", "生成纪要", "导出")


class StepState(Enum):
    """步骤状态。"""

    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"


@dataclass
class Step:
    """单个步骤。"""

    title: str
    state: StepState = StepState.PENDING


class FlowBar(QFrame):
    """5 步流程条。

    M1 骨架：所有步骤均可点击切换内容（便于测试占位视图）；
    生产环境的规则是「仅已完成步骤可点击回看」（docs/09 §4.1）。
    """

    step_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FlowBar")
        self._steps: list[Step] = [Step(title=t) for t in STEP_TITLES]
        self._buttons: list[QPushButton] = []
        self._connectors: list[QLabel] = []
        self._build()
        self.set_state(1, StepState.ACTIVE)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SIZING.space_md, SIZING.space_md, SIZING.space_md, SIZING.space_md)
        outer.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(SIZING.space_xs)
        for i in range(len(self._steps)):
            if i > 0:
                conn = QLabel("──")
                conn.setObjectName("StepConnector")
                conn.setProperty("done", "false")
                row.addWidget(conn)
                self._connectors.append(conn)
            btn = QPushButton("")
            btn.setObjectName("StepBtn")
            btn.setProperty("state", "pending")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            idx = i
            btn.clicked.connect(lambda _c=False, k=idx: self._on_click(k))
            row.addWidget(btn, 1)
            self._buttons.append(btn)

        outer.addLayout(row)

    def set_state(self, index: int, state: StepState) -> None:
        """设置指定步骤状态（1-based）。"""
        self._steps[index - 1].state = state
        self._refresh()

    def states(self) -> list[StepState]:
        """当前所有步骤状态（1-based 顺序）。"""
        return [s.state for s in self._steps]

    def current(self) -> int:
        """当前进行中的步骤号（1-based）；无则返回 1。"""
        for i, s in enumerate(self._steps):
            if s.state is StepState.ACTIVE:
                return i + 1
        return 1

    def _on_click(self, index: int) -> None:
        self.step_selected.emit(index)

    def _refresh(self) -> None:
        for i, (step, btn) in enumerate(zip(self._steps, self._buttons, strict=True)):
            btn.setText(f"{i + 1}. {step.title}")
            btn.setProperty("state", step.state.value)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        for i, conn in enumerate(self._connectors):
            done = self._steps[i].state is StepState.DONE
            conn.setProperty("done", "true" if done else "false")
            conn.style().unpolish(conn)
            conn.style().polish(conn)
