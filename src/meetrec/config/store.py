"""用户配置存储。

设计原则：
1. 原子写入：先写临时文件再 os.replace，崩溃不损坏配置。
2. Schema 版本化：不兼容版本抛 ConfigSchemaError（见 errors.py）。
3. 类型化访问 + 线程安全（RLock），后台任务与 UI 线程可并发。
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from meetrec.errors import ConfigError, ConfigSchemaError
from meetrec.paths import SCHEMA_VERSION, config_path


class ConfigStore:
    """JSON 配置文件读写，原子写入 + schema 版本化。"""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or config_path()
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self.load()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        """从磁盘加载配置；文件不存在时写入默认值。"""
        with self._lock:
            if not self._path.exists():
                self._data = {"schema_version": SCHEMA_VERSION}
                self._write()
                return
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise ConfigError(f"配置文件解析失败：{self._path}", details=str(exc)) from exc
            if not isinstance(raw, dict):
                raise ConfigError("配置文件顶层必须是对象", details=str(raw)[:200])
            version = int(raw.get("schema_version", 0))
            if version > SCHEMA_VERSION:
                raise ConfigSchemaError(
                    f"配置文件版本 {version} 高于当前支持版本 {SCHEMA_VERSION}",
                    details={"file_version": version, "supported": SCHEMA_VERSION},
                )
            self._data = raw

    def save(self) -> None:
        with self._lock:
            self._write()

    def _write(self) -> None:
        self._data["schema_version"] = SCHEMA_VERSION
        target_dir = self._path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix=".config_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_path, self._path)
        except OSError as exc:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise ConfigError(f"配置写入失败：{self._path}", details=str(exc)) from exc

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._write()

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._write()

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def reset(self) -> None:
        with self._lock:
            self._data = {"schema_version": SCHEMA_VERSION}
            self._write()

    def __repr__(self) -> str:
        return f"<ConfigStore path={self._path} keys={len(self._data)}>"
