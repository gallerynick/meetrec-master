"""主窗口：侧边栏 + 内容区。

对应 docs/09 §3.1 主窗口布局：
- 左侧侧边导航（232 px，可折叠）
- 右侧内容区（QStackedWidget，5 视图交叉切换）
- 窗口几何持久化（QSettings）
- 主题切换整体替换 QSS（无残留，docs/09 §2）
- 最小尺寸约束 1080 × 680（docs/09 §2.6）
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
)

from meetrec.paths import APP_NAME
from meetrec.ui.flow_bar import StepState
from meetrec.ui.sidebar import NAV_ITEMS, Sidebar
from meetrec.ui.theme import Theme, qss, theme_for
from meetrec.ui.views.about_view import AboutView
from meetrec.ui.views.keywords_view import KeywordsView
from meetrec.ui.views.library_view import LibraryView
from meetrec.ui.views.meeting_view import MeetingView
from meetrec.ui.views.settings_view import SettingsView

__all__ = ["MainWindow"]

_SETTINGS_GROUP = "window"
_NAV_KEYS: tuple[str, ...] = tuple(k for k, _, _ in NAV_ITEMS)


class MainWindow(QMainWindow):
    """主窗口。"""

    def __init__(self, dark: bool = False, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1080, 680)
        self.resize(1440, 900)

        self._dark = dark
        self._theme: Theme = theme_for(dark)

        # ── 侧边栏 + 5 视图（独立引用，保留类型信息）──
        self._sidebar = Sidebar()
        self._library = LibraryView()
        self._meeting = MeetingView()
        self._keywords = KeywordsView()
        self._about = AboutView()
        self._settings = SettingsView()
        self._views: dict[str, QFrame] = {
            "library": self._library,
            "meeting": self._meeting,
            "keywords": self._keywords,
            "about": self._about,
            "settings": self._settings,
        }
        self._stack = QStackedWidget()
        for key in _NAV_KEYS:
            self._stack.addWidget(self._views[key])
        self._stack.setCurrentWidget(self._library)

        root = QFrame()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(root)

        self._build_menu()

        # ── 信号连接 ──
        self._sidebar.nav_selected.connect(self._show_view)
        self._sidebar.new_meeting_clicked.connect(self._on_new_meeting)
        self._settings.theme_changed.connect(self.set_dark)
        self._library.new_meeting_requested.connect(self._on_new_meeting)

        # ── 主题 ──
        self._apply_theme(self._theme)

        # ── 几何持久化 ──
        self._persist = QSettings()
        self._restore_geometry()

    def _build_menu(self) -> None:
        """最小菜单栏（文件 + 帮助）。"""
        menu = self.menuBar()
        file_menu = menu.addMenu("文件")
        new_action = QAction("新建会议", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._on_new_meeting)
        file_menu.addAction(new_action)

        help_menu = menu.addMenu("帮助")
        about_action = QAction(f"关于 {APP_NAME}", self)
        about_action.triggered.connect(lambda: self._show_view("about"))
        help_menu.addAction(about_action)

    # ── 导航 ──

    def _show_view(self, key: str) -> None:
        """切换到指定视图。"""
        if key in self._views:
            self._stack.setCurrentWidget(self._views[key])

    def _on_new_meeting(self) -> None:
        """新建会议：切到会议详情并重置流程条。"""
        self._show_view("meeting")
        self._meeting.flow_bar().set_state(1, StepState.ACTIVE)

    def views(self) -> dict[str, QFrame]:
        """返回所有视图（供测试使用）。"""
        return self._views

    def sidebar(self) -> Sidebar:
        """返回侧边栏（供测试使用）。"""
        return self._sidebar

    # ── 主题 ──

    def _apply_theme(self, theme: Theme) -> None:
        """整体替换 QSS，保证无残留。"""
        self.setStyleSheet(qss(theme))
        self._theme = theme

    def set_dark(self, dark: bool) -> None:
        """切换明/暗主题。"""
        self._dark = dark
        self._apply_theme(theme_for(dark))
        self._settings.set_dark(dark)

    def is_dark(self) -> bool:
        return self._dark

    @property
    def theme(self) -> Theme:
        return self._theme

    # ── 几何持久化 ──

    def _restore_geometry(self) -> None:
        """从 QSettings 恢复窗口几何与侧边栏折叠状态。"""
        s = self._persist
        s.beginGroup(_SETTINGS_GROUP)
        geom = s.value("geometry")
        if geom:
            self.restoreGeometry(QByteArray(geom))
        collapsed = s.value("sidebar_collapsed", False, type=bool)
        s.endGroup()
        self._sidebar.set_collapsed(bool(collapsed))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """关闭时保存窗口几何与偏好。"""
        s = self._persist
        s.beginGroup(_SETTINGS_GROUP)
        s.setValue("geometry", self.saveGeometry().data())
        s.setValue("sidebar_collapsed", self._sidebar.is_collapsed())
        s.setValue("dark", self._dark)
        s.endGroup()
        super().closeEvent(event)
