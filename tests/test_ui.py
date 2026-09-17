"""UI 冒烟测试（offscreen 平台）。

覆盖 M1 退出条件：
- 窗口可启动（macOS 与 Windows 均能启动）
- 最小尺寸约束生效
- 侧边导航切换
- 侧边栏折叠
- 单实例锁
- 5 步流程条状态
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui


def test_main_window_smoke(qtbot):
    """主窗口可启动，5 个视图均注册。"""
    from meetrec.ui.main_window import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    qtbot.waitUntil(lambda: w.isVisible(), timeout=2000)
    assert len(w.views()) == 5
    for key in ("library", "meeting", "keywords", "about", "settings"):
        assert key in w.views()


def test_nav_switch(qtbot):
    """侧边导航可切换视图。"""
    from meetrec.ui.main_window import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    qtbot.waitUntil(lambda: w.isVisible(), timeout=2000)

    w._show_view("meeting")
    assert w._stack.currentWidget() is w.views()["meeting"]
    w._show_view("settings")
    assert w._stack.currentWidget() is w.views()["settings"]
    w._show_view("library")
    assert w._stack.currentWidget() is w.views()["library"]


def test_min_size_constraint(qtbot):
    """最小尺寸约束生效（1080 × 680）。"""
    from meetrec.ui.main_window import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    qtbot.waitUntil(lambda: w.isVisible(), timeout=2000)

    w.resize(400, 300)
    qtbot.waitUntil(lambda: w.width() >= 1080 and w.height() >= 680, timeout=2000)
    assert w.minimumWidth() == 1080
    assert w.minimumHeight() == 680


def test_sidebar_collapse(qtbot):
    """侧边栏可折叠（232 → 56 px）并可展开。"""
    from meetrec.ui.main_window import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)
    w.show()

    sidebar = w.sidebar()
    assert sidebar.width() == 232
    sidebar.set_collapsed(True)
    assert sidebar.width() == 56
    assert sidebar.is_collapsed() is True
    sidebar.set_collapsed(False)
    assert sidebar.width() == 232
    assert sidebar.is_collapsed() is False


def test_single_instance_lock(tmp_path, qtbot):
    """单实例锁：第二个实例无法获取锁，释放后可获取。"""
    from meetrec.ui.single_instance import SingleInstanceGuard

    lock = str(tmp_path / "test.lock")
    g1 = SingleInstanceGuard(lock_path=lock)
    g2 = SingleInstanceGuard(lock_path=lock)

    assert g1.try_acquire() is True
    assert g2.try_acquire() is False
    g1.release()
    assert g2.try_acquire() is True
    g2.release()
    assert g2.try_acquire() is True
    g2.release()


def test_flow_bar_states(qtbot):
    """5 步流程条状态正确。"""
    from meetrec.ui.flow_bar import FlowBar, StepState

    fb = FlowBar()
    qtbot.addWidget(fb)
    assert fb.states() == [
        StepState.ACTIVE,
        StepState.PENDING,
        StepState.PENDING,
        StepState.PENDING,
        StepState.PENDING,
    ]
    fb.set_state(1, StepState.DONE)
    fb.set_state(2, StepState.ACTIVE)
    assert fb.states() == [
        StepState.DONE,
        StepState.ACTIVE,
        StepState.PENDING,
        StepState.PENDING,
        StepState.PENDING,
    ]
    assert fb.current() == 2


def test_flow_bar_step_click(qtbot):
    """点击流程条步骤触发信号。"""
    from meetrec.ui.flow_bar import FlowBar

    fb = FlowBar()
    qtbot.addWidget(fb)
    clicks: list[int] = []
    fb.step_selected.connect(clicks.append)
    fb._on_click(3)
    assert clicks == [3]


def test_library_empty_state(qtbot):
    """会议库空态显示新建会议按钮。"""
    from meetrec.ui.service import MeetingService
    from meetrec.ui.views.library_view import LibraryView

    svc = MeetingService()
    v = LibraryView(svc)
    qtbot.addWidget(v)
    v.show()
    # 默认空态（无会议）
    assert v._stack.currentWidget() is v._empty


def test_meeting_view_step_switch(qtbot):
    """会议详情视图：流程条点击切换步骤内容。"""
    from meetrec.ui.service import MeetingService
    from meetrec.ui.views.meeting_view import MeetingView

    svc = MeetingService()
    v = MeetingView(svc)
    qtbot.addWidget(v)
    v.show()
    v._flow_bar._on_click(3)
    assert v._stack.currentIndex() == 3  # 0-based: step 4 → index 3
