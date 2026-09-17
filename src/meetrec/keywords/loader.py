"""热词加载。

支持两种格式：
1. 纯热词：每行一个热词
2. 带别名：热词 到 别名1, 别名2
"""

from __future__ import annotations

from pathlib import Path

from meetrec.errors import KeywordLoadError
from meetrec.paths import keywords_dir

__all__ = ["KeywordLoader"]

DEFAULT_FILE = "hotwords.txt"


class KeywordLoader:
    """热词文件加载与保存。"""

    def __init__(self, directory: Path | None = None) -> None:
        self._dir = directory or keywords_dir()
        self._dir.mkdir(parents=True, exist_ok=True)

    def load_from_file(self, path: str | Path) -> list[str]:
        """从文件加载热词（每行一个，支持 到 别名 格式）。"""
        path = Path(path)
        if not path.exists():
            raise KeywordLoadError(message=f"热词文件不存在：{path}")

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            raise KeywordLoadError(message=f"读取热词文件失败：{e}") from e

        hotwords: list[str] = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "到" in line:
                parts = line.split("到", 1)
                hw = parts[0].strip()
                aliases = [a.strip() for a in parts[1].split(",") if a.strip()]
                hotwords.append(hw)
                hotwords.extend(aliases)
            else:
                hotwords.append(line)

        return hotwords

    def load_default(self) -> list[str]:
        """加载默认热词文件。"""
        default = self._dir / DEFAULT_FILE
        if not default.exists():
            self.save([], DEFAULT_FILE)
            return []
        return self.load_from_file(default)

    def save(self, hotwords: list[str], filename: str = DEFAULT_FILE) -> Path:
        """保存热词到文件。"""
        path = self._dir / filename
        nl = chr(10)
        header = "# MeetRec Master 热词文件" + nl
        header += "# 每行一个热词，以 # 开头的是注释" + nl
        header += "# 支持格式：热词 到 别名1, 别名2" + nl
        content = header + nl.join(hotwords) + nl
        path.write_text(content, encoding="utf-8")
        return path

    def list_files(self) -> list[Path]:
        """列出所有热词文件。"""
        return sorted(self._dir.glob("*.txt"))
