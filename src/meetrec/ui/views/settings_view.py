"""设置视图。

M1 骨架：主题切换（明/暗）+ ASR 模型 / AI 提供方 / 数据目录占位。
主题切换即整体替换 QSS（docs/09 §2 设计令牌），无残留。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from meetrec import __version__
from meetrec.paths import data_dir
from meetrec.ui.theme import SIZING

__all__ = ["SettingsView"]


class SettingsView(QFrame):
    """设置视图：主题切换 + 占位配置项。"""

    theme_changed = Signal(bool)  # True = 深色

    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")
        self._dark = False

        root = QVBoxLayout(self)
        root.setContentsMargins(
            SIZING.space_2xl, SIZING.space_2xl, SIZING.space_2xl, SIZING.space_2xl
        )
        root.setSpacing(SIZING.space_xl)

        title = QLabel("设置")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # ── 外观 ──
        root.addWidget(self._section("外观"))
        theme_row = QVBoxLayout()
        self._theme_btn = QPushButton("切换为深色模式")
        self._theme_btn.setObjectName("Secondary")
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.clicked.connect(self._toggle_theme)
        theme_row.addWidget(self._theme_btn)
        root.addLayout(theme_row)

        # ── ASR 模型 ──
        root.addWidget(self._section("语音识别"))
        asr_desc = QLabel(
            "模型：large-v3-turbo（默认） · 809M 参数 · MIT 许可\nM3 交付：应用内模型下载与切换。"
        )
        asr_desc.setObjectName("EmptySubtitle")
        asr_desc.setWordWrap(True)
        root.addWidget(asr_desc)

        # ── AI 提供方 ──
        root.addWidget(self._section("纪要生成"))
        ai_desc = QLabel(
            "OpenAI / Anthropic / DeepSeek / 本地 Ollama\nM5 交付：API Key 管理与切换。"
        )
        ai_desc.setObjectName("EmptySubtitle")
        ai_desc.setWordWrap(True)
        root.addWidget(ai_desc)

        # ── 数据目录 ──
        root.addWidget(self._section("存储"))
        data_lbl = QLabel(f"数据目录：{data_dir()}\n版本：{__version__}")
        data_lbl.setObjectName("Caption")
        data_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(data_lbl)

        root.addStretch()

    def _section(self, text: str) -> QLabel:
        """小节标题。"""
        lbl = QLabel(text)
        lbl.setObjectName("PageTitle")
        lbl.setStyleSheet("font-size: 17px;")
        return lbl

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._theme_btn.setText("切换为浅色模式" if self._dark else "切换为深色模式")
        self.theme_changed.emit(self._dark)

    def is_dark(self) -> bool:
        """当前设置面板中记录的主题（深色 = True）。"""
        return self._dark

    def set_dark(self, dark: bool) -> None:
        """由主窗口同步主题状态（不触发回调）。"""
        self._dark = dark
        self._theme_btn.setText("切换为浅色模式" if dark else "切换为深色模式")
