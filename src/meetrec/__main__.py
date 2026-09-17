"""MeetRec Master 命令行入口。

M1 起：默认启动 PySide6 UI；--info / --version 为诊断命令。
单实例锁保证同一时间只运行一个实例（QLockFile）。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from meetrec import __version__
from meetrec.paths import APP_NAME, data_dir


def _info() -> int:
    """打印环境诊断信息。"""
    print(f"MeetRec Master {__version__}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")
    print(f"Data dir: {data_dir()}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="meetrec",
        description="MeetRec Master - 本地离线 ASR + 热词四阶段纠错 + 多 AI 纪要",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--info",
        action="store_true",
        help="显示数据目录与环境信息（用于诊断与反馈）",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="仅初始化，不启动 UI（用于脚本集成）",
    )
    args = parser.parse_args(argv)

    if args.info:
        return _info()
    if args.no_gui:
        print(f"MeetRec Master {__version__} 初始化完成（无 GUI）。")
        return 0

    # ── 启动 UI ──
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from meetrec.log import setup_logging
    from meetrec.ui.main_window import MainWindow
    from meetrec.ui.single_instance import SingleInstanceGuard

    guard = SingleInstanceGuard()
    if not guard.try_acquire():
        print("MeetRec Master 已在运行。")
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("MeetRec")
    app.setOrganizationDomain("meetrec.io")

    setup_logging()

    s = QSettings()
    s.beginGroup("window")
    dark = s.value("dark", False, type=bool)
    s.endGroup()

    window = MainWindow(dark=bool(dark))
    window.show()
    code = app.exec()
    guard.release()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
