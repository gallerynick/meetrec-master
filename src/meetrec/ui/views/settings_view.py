"""设置视图。

M2–M6 后接真实配置：主题切换、ASR 模型、AI API Key 管理、数据目录。
"""

from __future__ import annotations

import contextlib

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from meetrec import __version__
from meetrec.paths import data_dir
from meetrec.secrets.vault import SecretVault
from meetrec.ui.theme import SIZING

__all__ = ["SettingsView"]


class SettingsView(QFrame):
    """设置视图：主题切换 + API Key 管理 + 存储信息。"""

    theme_changed = Signal(bool)

    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")
        self._dark = False
        self._vault = SecretVault()

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
            "默认模型：large-v3-turbo（809M 参数）· MIT 许可\n"
            "可在「转写」步骤中选择模型，首次使用自动下载。"
        )
        asr_desc.setObjectName("EmptySubtitle")
        asr_desc.setWordWrap(True)
        root.addWidget(asr_desc)

        # ── AI API Key 管理 ──
        root.addWidget(self._section("纪要生成 · API Key"))
        ai_panel = QFrame()
        ai_panel.setObjectName("card")
        ai_layout = QVBoxLayout(ai_panel)
        ai_layout.setSpacing(8)
        ai_layout.setContentsMargins(16, 12, 16, 12)

        for provider in ("openai", "anthropic", "deepseek"):
            row = QVBoxLayout()
            row.setSpacing(4)
            name_label = QLabel(f"{provider} API Key")
            name_label.setStyleSheet("font-size: 12px; font-weight: 600;")
            row.addWidget(name_label)

            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setPlaceholderText(f"输入 {provider} API Key…")
            edit.setFixedHeight(28)

            save_btn = QPushButton("保存")
            save_btn.setFixedHeight(28)
            save_btn.setMaximumWidth(60)
            save_btn.clicked.connect(
                lambda checked, p=provider, e=edit: self._save_api_key(p, e.text().strip())
            )

            row_layout = QVBoxLayout()
            row_layout.setSpacing(4)
            row_layout.addWidget(edit)
            row_layout.addWidget(save_btn, 0, Qt.AlignmentFlag.AlignLeft)
            row.addLayout(row_layout)
            ai_layout.addLayout(row)

        root.addWidget(ai_panel)

        # ── 数据目录 ──
        root.addWidget(self._section("存储"))
        data_lbl = QLabel(f"数据目录：{data_dir()}\n版本：{__version__}")
        data_lbl.setObjectName("Caption")
        data_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(data_lbl)

        root.addStretch()

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("PageTitle")
        lbl.setStyleSheet("font-size: 17px;")
        return lbl

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._theme_btn.setText("切换为浅色模式" if self._dark else "切换为深色模式")
        self.theme_changed.emit(self._dark)

    def _save_api_key(self, provider: str, key: str) -> None:
        if not key:
            return
        with contextlib.suppress(Exception):
            self._vault.set(f"ai_{provider}", key)

    def is_dark(self) -> bool:
        return self._dark

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self._theme_btn.setText("切换为浅色模式" if dark else "切换为深色模式")
