"""config/store.py 单元测试。"""

from __future__ import annotations

import json

import pytest

from meetrec.config.store import ConfigStore
from meetrec.errors import ConfigError, ConfigSchemaError


def test_roundtrip_set_get_delete(tmp_path):
    store = ConfigStore(path=tmp_path / "config.json")
    store.set("asr.model", "large-v3-turbo")
    store.set("ui.language", "zh-CN")
    assert store.get("asr.model") == "large-v3-turbo"
    assert store.get("ui.language") == "zh-CN"
    assert store.get("missing", "default") == "default"
    store.delete("asr.model")
    assert store.get("asr.model") is None


def test_reload_from_disk(tmp_path):
    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    store.set("theme", "dark")

    store2 = ConfigStore(path=path)
    assert store2.get("theme") == "dark"


def test_atomic_write_creates_schema_version(tmp_path):
    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    store.set("x", 1)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1


def test_corrupt_json_raises_config_error(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        ConfigStore(path=path)


def test_higher_schema_raises(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(ConfigSchemaError):
        ConfigStore(path=path)


def test_reset_clears_keys(tmp_path):
    store = ConfigStore(path=tmp_path / "config.json")
    store.set("a", 1)
    store.reset()
    assert store.get("a") is None


def test_all_returns_copy(tmp_path):
    store = ConfigStore(path=tmp_path / "config.json")
    store.set("a", 1)
    all_data = store.all()
    all_data["a"] = 999  # 修改副本不影响内部
    assert store.get("a") == 1
