"""关键词库视图（占位）。

对应 docs/09 §3.2：关键词库是底部入口。
M1 骨架：分组树（人名/产品名/术语/其他），颜色取自 docs/09 §2.2。
"""

from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from meetrec.ui.theme import SIZING

__all__ = ["KeywordsView"]

_GROUPS: tuple[tuple[str, str, str], ...] = (
    ("人名", "与会者、客户、合作方姓名", "#E3F2FD"),
    ("产品名", "产品、模块、功能名", "#E8F5E9"),
    ("术语", "技术术语、行业词汇", "#FFF3E0"),
    ("其他", "未归类的关键词", "#F3E5F5"),
)


class KeywordsView(QFrame):
    """关键词库视图：分组树 + 空态说明。"""

    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")

        root = QVBoxLayout(self)
        root.setContentsMargins(
            SIZING.space_2xl, SIZING.space_2xl, SIZING.space_2xl, SIZING.space_2xl
        )
        root.setSpacing(SIZING.space_md)

        title = QLabel("关键词库")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        subtitle = QLabel("分组管理热词，用于转写后的定向重解码与校正。")
        subtitle.setObjectName("EmptySubtitle")
        root.addWidget(subtitle)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(SIZING.space_lg)
        self._build_groups()
        root.addWidget(self._tree, 1)

    def _build_groups(self) -> None:
        """填充 4 个分组（M3 替换为真实热词加载）。"""
        for name, desc, color in _GROUPS:
            group = QTreeWidgetItem([f"●  {name}"])
            group.setToolTip(0, desc)
            group.setBackground(0, QColor(color))
            self._tree.addTopLevelItem(group)
            empty = QTreeWidgetItem(["（空 — M3 交付热词加载）"])
            empty.setForeground(0, QBrush(QColor("#8E8E93")))
            self._tree.addTopLevelItem(empty)
