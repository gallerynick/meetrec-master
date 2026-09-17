"""共享测试夹具。

关键原则：
- 所有测试使用 tmp_path 隔离，绝不写入真实用户数据目录（避免污染 ~/Library/...）。
- 通过 monkeypatch 重定向 paths.data_dir，其余目录函数均派生自 data_dir。
"""

from __future__ import annotations

import pytest


@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    """把 meetrec.paths.data_dir 重定向到 tmp_path。"""
    import meetrec.paths as paths

    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    return tmp_path
