"""共享测试夹具。

关键原则：
- 所有测试使用 tmp_path 隔离，绝不写入真实用户数据目录（避免污染 ~/Library/...）。
- 通过 monkeypatch 重定向 paths.data_dir，其余目录函数均派生自 data_dir。
- Qt 测试使用 offscreen 平台（CI 无显示设备）。
"""

from __future__ import annotations

import os

# 必须在导入 PySide6 之前设置（offscreen 平台，CI/本地均无显示设备）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    """把 meetrec.paths.data_dir 重定向到 tmp_path。"""
    import meetrec.paths as paths

    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    return tmp_path
