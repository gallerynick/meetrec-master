"""侧边导航。

对应 docs/09 §3.1–3.2：
- 固定 232 px，可折叠至 56 px
- 会议库为主导航，关键词库/关于/设置为底部入口
- 「设置」永远在最底部
- 选中态 accent 12% 底色 + accent 文字；悬停态 card-bg 底色
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from meetrec.ui.theme import SIZING

__all__ = ["NAV_ITEMS", "Sidebar"]

# (key, 完整标签, 折叠态单字标记)
NAV_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("library", "会议库", "库"),
    ("meeting", "会议详情", "详"),
    ("keywords", "关键词库", "词"),
    ("about", "关于", "关"),
    ("settings", "设置", "设"),
)

# 主导航（顶部）与底部入口的划分
_MAIN_COUNT = 3


class Sidebar(QFrame):
    """侧边导航栏。"""

    nav_selected = Signal(str)  # 选中的导航 key
    new_meeting_clicked = Signal()  # 新建会议
    collapsed_changed = Signal(bool)  # 折叠状态变化

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIZING.sidebar_width)
        self._collapsed = False
        self._nav_buttons: dict[str, QPushButton] = {}
        self._nav_meta: dict[str, tuple[str, str]] = {}
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SIZING.space_md, SIZING.space_lg, SIZING.space_md, SIZING.space_md)
        root.setSpacing(SIZING.space_xs)

        # 应用标题
        title = QLabel("MeetRec Master")
        title.setObjectName("AppTitle")
        root.addWidget(title)
        root.addSpacing(SIZING.space_md)

        # 新建会议（主操作）
        new_btn = QPushButton("+ 新建会议")
        new_btn.setObjectName("NewMeeting")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self.new_meeting_clicked)
        root.addWidget(new_btn)
        root.addSpacing(SIZING.space_md)

        # 主导航
        for key, label, compact in NAV_ITEMS[:_MAIN_COUNT]:
            root.addWidget(self._make_nav(key, label, compact))

        root.addStretch()

        # 底部入口（设置永远在最后）
        for key, label, compact in NAV_ITEMS[_MAIN_COUNT:]:
            root.addWidget(self._make_nav(key, label, compact))

        # 折叠按钮
        toggle = QPushButton("< >")
        toggle.setObjectName("IconBtn")
        toggle.setFixedWidth(SIZING.control_height)
        toggle.setToolTip("折叠/展开侧边栏")
        toggle.clicked.connect(self._toggle_collapsed)
        root.addWidget(toggle)

        # 默认选中会议库
        self._select("library")

    def _make_nav(self, key: str, label: str, compact: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("NavItem")
        btn.setProperty("selected", "false")
        btn.setProperty("compact", "false")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _checked=False, k=key: self._select(k))
        self._nav_buttons[key] = btn
        self._nav_meta[key] = (label, compact)
        return btn

    def _select(self, key: str) -> None:
        for k, btn in self._nav_buttons.items():
            btn.setProperty("selected", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.nav_selected.emit(key)

    def set_collapsed(self, collapsed: bool) -> None:
        """设置折叠状态（宽度 232 → 56 px）。"""
        self._collapsed = collapsed
        self.setFixedWidth(SIZING.sidebar_collapsed_width if collapsed else SIZING.sidebar_width)
        for key, btn in self._nav_buttons.items():
            label, compact = self._nav_meta[key]
            btn.setText(compact if collapsed else label)
            btn.setProperty("compact", "true" if collapsed else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.collapsed_changed.emit(collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)
