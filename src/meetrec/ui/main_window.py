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
from meetrec.ui.service import MeetingService
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

        # ── 服务层 ──
        self._service = MeetingService()

        # ── 侧边栏 + 5 视图 ──
        self._sidebar = Sidebar()
        self._library = LibraryView(self._service)
        self._meeting = MeetingView(self._service)
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
        self._library.meeting_selected.connect(self._on_meeting_selected)

        # ── 主题 ──
        self._apply_theme(self._theme)

        # ── 几何持久化 ──
        self._persist = QSettings()
        self._restore_geometry()

    def _build_menu(self) -> None:
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

    def _show_view(self, key: str) -> None:
        if key in self._views:
            self._stack.setCurrentWidget(self._views[key])

    def _on_new_meeting(self) -> None:
        self._meeting.new_meeting()
        self._show_view("meeting")

    def _on_meeting_selected(self, meeting_id: str) -> None:
        meeting = self._service.get_meeting(meeting_id)
        if meeting:
            self._meeting.load_meeting(meeting)
            self._show_view("meeting")

    def views(self) -> dict[str, QFrame]:
        return self._views

    def sidebar(self) -> Sidebar:
        return self._sidebar

    def service(self) -> MeetingService:
        return self._service

    def _apply_theme(self, theme: Theme) -> None:
        self.setStyleSheet(qss(theme))
        self._theme = theme

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self._apply_theme(theme_for(dark))
        self._settings.set_dark(dark)

    def is_dark(self) -> bool:
        return self._dark

    @property
    def theme(self) -> Theme:
        return self._theme

    def _restore_geometry(self) -> None:
        s = self._persist
        s.beginGroup(_SETTINGS_GROUP)
        geom = s.value("geometry")
        if geom:
            self.restoreGeometry(QByteArray(geom))
        collapsed = s.value("sidebar_collapsed", False, type=bool)
        s.endGroup()
        self._sidebar.set_collapsed(bool(collapsed))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        s = self._persist
        s.beginGroup(_SETTINGS_GROUP)
        s.setValue("geometry", self.saveGeometry().data())
        s.setValue("sidebar_collapsed", self._sidebar.is_collapsed())
        s.setValue("dark", self._dark)
        s.endGroup()
        super().closeEvent(event)
