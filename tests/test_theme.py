"""主题切换无残留测试。

覆盖 M1 退出条件：主题切换后旧主题颜色不得残留。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui


def test_qss_replaces_all_tokens():
    """QSS 生成后无残留占位符。"""
    from meetrec.ui.theme import DARK, LIGHT, qss

    for t in (LIGHT, DARK):
        s = qss(t)
        assert "__font__" not in s
        assert "__sidebar_bg__" not in s
        assert "__accent__" not in s
        assert t.colors.accent in s
        assert t.colors.sidebar_bg in s
        assert t.colors.text_primary in s


def test_qss_accent_alpha():
    """accent 12% 透明度正确生成。"""
    from meetrec.ui.theme import DARK, LIGHT, qss

    for t in (LIGHT, DARK):
        s = qss(t)
        assert "rgba(10, 132, 255, 0.12)" in s


def test_theme_switch_no_residue(qtbot):
    """切换主题后样式表完全等于新主题 QSS（整体替换，无残留）。"""
    from meetrec.ui.main_window import MainWindow
    from meetrec.ui.theme import DARK, LIGHT, qss

    w = MainWindow(dark=False)
    qtbot.addWidget(w)
    w.show()

    # 初始：样式表 == 浅色 QSS
    assert w.styleSheet() == qss(LIGHT)

    # 切换深色：样式表 == 深色 QSS（完整替换）
    w.set_dark(True)
    assert w.styleSheet() == qss(DARK)
    assert w.is_dark() is True

    # 切回浅色：样式表 == 浅色 QSS
    w.set_dark(False)
    assert w.styleSheet() == qss(LIGHT)
    assert w.is_dark() is False


def test_theme_toggle_no_accumulation(qtbot):
    """多次切换主题后样式表长度稳定（无累积）。"""
    from meetrec.ui.main_window import MainWindow

    w = MainWindow(dark=False)
    qtbot.addWidget(w)
    w.show()

    first_len = len(w.styleSheet())
    for i in range(10):
        w.set_dark(i % 2 == 1)
    assert len(w.styleSheet()) == first_len


def test_settings_theme_callback(qtbot):
    """设置视图主题按钮触发回调并更新文案。"""
    from meetrec.ui.main_window import MainWindow

    w = MainWindow(dark=False)
    qtbot.addWidget(w)
    w.show()

    settings = w.views()["settings"]
    assert settings.is_dark() is False
    settings._theme_btn.setText("切换为浅色模式")
    w.set_dark(True)
    assert settings.is_dark() is True
    assert settings._theme_btn.text() == "切换为浅色模式"
