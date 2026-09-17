"""跨平台路径解析。

数据根目录（ADR-006：SQLite 作索引，内容以文件系统存放）：
- macOS:   ~/Library/Application Support/MeetRecMaster/
- Windows: %APPDATA%/MeetRecMaster/
- Linux:   ~/.local/share/MeetRecMaster/（XDG_DATA_HOME 优先）

约定：
- 不带 ensure 的函数仅返回路径，不创建目录（调用方按需创建）。
- 带 ensure 的函数（_dir 后缀）会自动创建目录并返回。
- 所有路径均为绝对路径，可直接用于 IO。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "MeetRecMaster"
BUNDLE_ID = "io.meetrec.master"
SCHEMA_VERSION = 1


def data_dir() -> Path:
    """应用数据根目录（不自动创建）。"""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / APP_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_NAME


def ensure_dir(path: Path) -> Path:
    """确保目录存在并返回。"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    """ASR 模型目录（ADR-009：不打包，按需下载）。"""
    return ensure_dir(data_dir() / "models")


def meetings_dir() -> Path:
    """会议数据目录（每会议一个子目录，见 07 章数据模型）。"""
    return ensure_dir(data_dir() / "meetings")


def keywords_dir() -> Path:
    """关键词库目录。"""
    return ensure_dir(data_dir() / "keywords")


def logs_dir() -> Path:
    """日志目录（ADR-010：滚动 5×1 MB）。"""
    return ensure_dir(data_dir() / "logs")


def trash_dir() -> Path:
    """回收站目录（ADR-006：删除进入此处，30 天后清理）。"""
    return ensure_dir(data_dir() / ".trash")


def config_path() -> Path:
    """用户配置 JSON 路径（不自动创建父目录）。"""
    return data_dir() / "config.json"


def vault_path() -> Path:
    """密钥加密文件路径（ADR-007 降级方案）。"""
    return data_dir() / "vault.enc"


def export_dir() -> Path:
    """默认导出目录（用户目录下的 Downloads，跨平台通用）。"""
    return Path.home() / "Downloads"
