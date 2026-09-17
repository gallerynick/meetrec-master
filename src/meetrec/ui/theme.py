"""设计令牌与主题。

对应 docs/09-ui-design-spec.md §2（设计令牌）与 §6（组件映射）。
- 间距遵守 8 pt 基准网格（4 的倍数）
- 颜色、圆角、字号、尺寸均取自规格表
- QSS 由模板 + 令牌值生成，明暗主题无残留（切换即整体替换）
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

__all__ = [
    "DARK",
    "FONT",
    "LIGHT",
    "MONO_FONT",
    "SIZING",
    "ColorTokens",
    "SizingTokens",
    "Theme",
    "qss",
    "rgba",
    "theme_for",
]


@dataclass(frozen=True)
class ColorTokens:
    """颜色令牌（docs/09 §2.1）。"""

    window_bg: str
    sidebar_bg: str
    content_bg: str
    card_bg: str
    border: str
    text_primary: str
    text_secondary: str
    text_tertiary: str
    accent: str
    accent_pressed: str
    success: str
    warning: str
    error: str
    info: str


@dataclass(frozen=True)
class SizingTokens:
    """尺寸令牌（docs/09 §2.3–2.6，单位 px）。"""

    space_xs: int = 4
    space_sm: int = 8
    space_md: int = 12
    space_lg: int = 16
    space_xl: int = 24
    space_2xl: int = 32
    space_3xl: int = 48
    radius_sm: int = 4
    radius_md: int = 8
    radius_lg: int = 12
    control_height: int = 28
    sidebar_width: int = 232
    sidebar_collapsed_width: int = 56
    min_window_w: int = 1080
    min_window_h: int = 680
    default_window_w: int = 1440
    default_window_h: int = 900
    titlebar_height: int = 38


SIZING = SizingTokens()

if sys.platform == "win32":
    FONT = "Segoe UI, 'Microsoft YaHei UI', sans-serif"
    MONO_FONT = "'Cascadia Code', Consolas, Menlo, monospace"
else:
    FONT = "-apple-system, 'PingFang SC', sans-serif"
    MONO_FONT = "'SF Mono', 'Cascadia Code', Consolas, Menlo, monospace"


LIGHT_COLORS = ColorTokens(
    window_bg="#FFFFFF",
    sidebar_bg="#F5F5F7",
    content_bg="#FFFFFF",
    card_bg="#FAFAFA",
    border="#E2E2E7",
    text_primary="#1D1D1F",
    text_secondary="#6E6E73",
    text_tertiary="#8E8E93",
    accent="#0A84FF",
    accent_pressed="#0060DF",
    success="#34C759",
    warning="#FF9F0A",
    error="#FF3B30",
    info="#64D2FF",
)

DARK_COLORS = ColorTokens(
    window_bg="#1E1E1E",
    sidebar_bg="#161616",
    content_bg="#1E1E1E",
    card_bg="#2A2A2A",
    border="#38383A",
    text_primary="#F5F5F7",
    text_secondary="#A1A1A6",
    text_tertiary="#6E6E73",
    accent="#0A84FF",
    accent_pressed="#0060DF",
    success="#30D158",
    warning="#FFD60A",
    error="#FF453A",
    info="#64D2FF",
)


@dataclass(frozen=True)
class Theme:
    """主题 = 颜色令牌 + 尺寸令牌 + 名称。"""

    name: str
    colors: ColorTokens
    dark: bool


LIGHT = Theme("light", LIGHT_COLORS, dark=False)
DARK = Theme("dark", DARK_COLORS, dark=True)


def theme_for(dark: bool) -> Theme:
    """按开关返回主题实例。"""
    return DARK if dark else LIGHT


def rgba(hex_color: str, alpha: float) -> str:
    """把 #RRGGBB 转成 rgba(r, g, b, alpha)，用于 accent 12% 选中底色。"""
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


_QSS_TEMPLATE = """
* {
    font-family: __font__;
    font-size: 13px;
}

QMainWindow, QWidget {
    background-color: __window_bg__;
    color: __text_primary__;
}

QMainWindow {
    background-color: __window_bg__;
}

/* ── 侧边栏 ──────────────────────────────────────────────── */
QFrame#Sidebar {
    background-color: __sidebar_bg__;
    border-right: 1px solid __border__;
}

QLabel#AppTitle {
    font-size: 15px;
    font-weight: 600;
    color: __text_primary__;
}

QPushButton#NewMeeting {
    height: __control_height__px;
    border-radius: __radius_md__px;
    background-color: __accent__;
    color: #FFFFFF;
    border: none;
    padding: 0 __space_md__px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#NewMeeting:pressed {
    background-color: __accent_pressed__;
}

QPushButton#NavItem {
    height: __control_height__px;
    text-align: left;
    border-radius: __radius_md__px;
    border: none;
    background-color: transparent;
    color: __text_secondary__;
    padding: 0 __space_md__px;
    font-size: 13px;
    font-weight: 400;
}

QPushButton#NavItem:hover {
    background-color: __card_bg__;
    color: __text_primary__;
}

QPushButton#NavItem[selected="true"] {
    background-color: __accent_alpha12__;
    color: __accent__;
    font-weight: 600;
}

QPushButton#NavItem[compact="true"] {
    text-align: center;
    padding: 0 __space_xs__px;
    font-weight: 600;
}

QLabel#Divider {
    background-color: __border__;
    max-height: 1px;
    min-height: 1px;
    margin: __space_sm__px __space_lg__px;
}

/* ── 内容区 ──────────────────────────────────────────────── */
QFrame#Content {
    background-color: __content_bg__;
}

QLabel#PageTitle {
    font-size: 22px;
    font-weight: 600;
    color: __text_primary__;
}

QLabel#EmptyTitle {
    font-size: 28px;
    font-weight: 600;
    color: __text_primary__;
}

QLabel#EmptySubtitle {
    font-size: 13px;
    color: __text_secondary__;
}

QLabel#Placeholder {
    color: __text_tertiary__;
    font-size: 13px;
}

QLabel#Caption {
    font-size: 11px;
    color: __text_secondary__;
}

/* ── 5 步流程条 ──────────────────────────────────────────── */
QFrame#FlowBar {
    background-color: __card_bg__;
    border-radius: __radius_lg__px;
    border: 1px solid __border__;
    padding: __space_md__px;
}

QPushButton#StepBtn {
    height: __control_height__px;
    border-radius: __radius_md__px;
    border: 1px solid __border__;
    background-color: transparent;
    color: __text_tertiary__;
    padding: 0 __space_md__px;
    font-size: 13px;
}

QPushButton#StepBtn[state="active"] {
    background-color: __accent__;
    color: #FFFFFF;
    border-color: __accent__;
    font-weight: 600;
}

QPushButton#StepBtn[state="done"] {
    background-color: __success__;
    color: #FFFFFF;
    border-color: __success__;
}

QPushButton#StepBtn[clickable="false"] {
    color: __text_tertiary__;
    cursor: default;
}

QLabel#StepConnector {
    color: __border__;
    font-size: 13px;
}

QLabel#StepConnector[done="true"] {
    color: __success__;
}

/* ── 通用按钮 ────────────────────────────────────────────── */
QPushButton#Primary {
    height: __control_height__px;
    border-radius: __radius_md__px;
    background-color: __accent__;
    color: #FFFFFF;
    border: none;
    padding: 0 __space_lg__px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#Primary:pressed {
    background-color: __accent_pressed__;
}

QPushButton#Primary:disabled {
    color: __text_tertiary__;
    background-color: __card_bg__;
}

QPushButton#Secondary {
    height: __control_height__px;
    border-radius: __radius_md__px;
    background-color: __card_bg__;
    border: 1px solid __border__;
    color: __text_primary__;
    padding: 0 __space_lg__px;
    font-size: 13px;
}

QPushButton#Secondary:hover {
    border-color: __accent__;
}

QPushButton#IconBtn {
    width: 28px;
    height: 28px;
    border-radius: __radius_md__px;
    border: none;
    background-color: transparent;
    color: __text_secondary__;
}

QPushButton#IconBtn:hover {
    background-color: __card_bg__;
    color: __text_primary__;
}

/* ── 输入控件 ────────────────────────────────────────────── */
QLineEdit, QComboBox {
    height: __control_height__px;
    border-radius: __radius_sm__px;
    border: 1px solid __border__;
    background-color: __card_bg__;
    padding: 0 __space_sm__px;
    color: __text_primary__;
}

QLineEdit:focus, QComboBox:focus {
    border: 2px solid __accent__;
    padding: 0 7px;
}

QCheckBox {
    spacing: 8px;
    color: __text_primary__;
}

/* ── 滚动条 ──────────────────────────────────────────────── */
QScrollBar:vertical {
    width: 10px;
    background: transparent;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: __border__;
    border-radius: 5px;
    min-height: 24px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    height: 10px;
    background: transparent;
}

QScrollBar::handle:horizontal {
    background: __border__;
    border-radius: 5px;
    min-width: 24px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── 菜单 / 提示 / 状态栏 ────────────────────────────────── */
QMenu {
    background-color: __card_bg__;
    border: 1px solid __border__;
    border-radius: __radius_md__px;
    padding: __space_xs__px;
}

QMenu::item {
    padding: 6px 12px;
    border-radius: __radius_sm__px;
}

QMenu::item:selected {
    background-color: __accent_alpha12__;
    color: __accent__;
}

QMenu::separator {
    height: 1px;
    background-color: __border__;
    margin: 4px __space_sm__px;
}

QToolTip {
    background-color: __card_bg__;
    color: __text_primary__;
    border: 1px solid __border__;
    border-radius: __radius_md__px;
    padding: __space_sm__px;
}

QStatusBar {
    background-color: __card_bg__;
    color: __text_secondary__;
    border-top: 1px solid __border__;
}
"""


def _token_map(t: Theme) -> dict[str, str]:
    """把主题令牌展平成占位符映射表。"""
    c = t.colors
    s = SIZING
    return {
        "window_bg": c.window_bg,
        "sidebar_bg": c.sidebar_bg,
        "content_bg": c.content_bg,
        "card_bg": c.card_bg,
        "border": c.border,
        "text_primary": c.text_primary,
        "text_secondary": c.text_secondary,
        "text_tertiary": c.text_tertiary,
        "accent": c.accent,
        "accent_pressed": c.accent_pressed,
        "accent_alpha12": rgba(c.accent, 0.12),
        "accent_alpha08": rgba(c.accent, 0.08),
        "success": c.success,
        "warning": c.warning,
        "error": c.error,
        "info": c.info,
        "font": FONT,
        "mono": MONO_FONT,
        "radius_sm": str(s.radius_sm),
        "radius_md": str(s.radius_md),
        "radius_lg": str(s.radius_lg),
        "control_height": str(s.control_height),
        "sidebar_width": str(s.sidebar_width),
        "sidebar_collapsed_width": str(s.sidebar_collapsed_width),
        "titlebar_height": str(s.titlebar_height),
        "space_xs": str(s.space_xs),
        "space_sm": str(s.space_sm),
        "space_md": str(s.space_md),
        "space_lg": str(s.space_lg),
        "space_xl": str(s.space_xl),
        "space_2xl": str(s.space_2xl),
        "space_3xl": str(s.space_3xl),
    }


def qss(t: Theme) -> str:
    """生成 QSS 样式表。

    模板中的 ``__token__`` 占位符按令牌值替换；CSS 花括号保持原样。
    """
    mapping = _token_map(t)

    def _repl(m: re.Match[str]) -> str:
        return mapping.get(m.group(1), m.group(0))

    return re.sub(r"__([a-z_0-9]+)__", _repl, _QSS_TEMPLATE)
