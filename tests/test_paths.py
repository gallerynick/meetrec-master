"""paths.py 单元测试。"""

from __future__ import annotations

from pathlib import Path

import meetrec.paths as paths


def test_data_dir_default_is_absolute():
    assert paths.data_dir().is_absolute()


def test_derived_dirs_live_under_data_dir(fake_data_dir):
    assert paths.models_dir().parent == fake_data_dir
    assert paths.meetings_dir().parent == fake_data_dir
    assert paths.logs_dir().parent == fake_data_dir
    assert paths.config_path().parent == fake_data_dir
    assert paths.vault_path().parent == fake_data_dir


def test_dir_functions_create_directories(fake_data_dir):
    assert paths.models_dir().is_dir()
    assert paths.meetings_dir().is_dir()
    assert paths.logs_dir().is_dir()
    assert paths.trash_dir().is_dir()


def test_export_dir_is_downloads():
    assert paths.export_dir() == Path.home() / "Downloads"


def test_ensure_dir_is_idempotent(fake_data_dir):
    p = fake_data_dir / "a" / "b"
    assert paths.ensure_dir(p) == p
    assert paths.ensure_dir(p) == p  # 不报错
