"""MeetRec Master 命令行入口。

M0 阶段仅提供版本与路径诊断，完整 CLI 在 M1 起实现。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from meetrec import __version__
from meetrec.paths import data_dir


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
    args = parser.parse_args(argv)

    if args.info:
        print(f"MeetRec Master {__version__}")
        print(f"Python: {sys.version.split()[0]}")
        print(f"Platform: {sys.platform}")
        print(f"Data dir: {data_dir()}")
        return 0

    print(f"MeetRec Master {__version__} (M0 skeleton)")
    print("完整 UI 将在 M1 交付；当前可用命令：--info / --version")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
