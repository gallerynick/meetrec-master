"""关于视图。

显示版本、Bundle ID、运行环境与数据目录。
"""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt, qVersion
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
)

from meetrec import __version__
from meetrec.paths import APP_NAME, BUNDLE_ID, data_dir
from meetrec.ui.theme import SIZING

__all__ = ["AboutView"]


class AboutView(QFrame):
    """关于视图。"""

    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")

        root = QVBoxLayout(self)
        root.setContentsMargins(
            SIZING.space_2xl, SIZING.space_3xl, SIZING.space_2xl, SIZING.space_2xl
        )
        root.setSpacing(SIZING.space_md)
        root.addStretch()

        name = QLabel(APP_NAME)
        name.setObjectName("EmptyTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(name)

        ver = QLabel(f"版本 {__version__} · {BUNDLE_ID}")
        ver.setObjectName("EmptySubtitle")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(ver)

        root.addSpacing(SIZING.space_xl)
        info = self._build_info()
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        root.addWidget(info)

        root.addStretch()

    def _build_info(self) -> QLabel:
        """运行环境信息（mono 字体，便于技术排查）。"""
        lines = [
            f"Python {platform.python_version()} · Qt {qVersion()!s}",
            f"平台：{platform.system()} {platform.machine()}",
            f"数据目录：{data_dir()}",
        ]
        lbl = QLabel(" | ".join(lines))
        lbl.setObjectName("Caption")
        lbl.setStyleSheet("font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;")
        return lbl
