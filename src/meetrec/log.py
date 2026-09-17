"""日志系统：默认 INFO，滚动 5x1 MB，全局脱敏。

脱敏规则（ADR-010）：
1. API Key / Bearer Token / Authorization header -> 整体替换为 ***
2. JSON 字段中的 api_key / token / secret -> 值替换为 ***
3. Prompt / content / system / messages 正文（>=20 字符）-> 仅保留长度与 SHA-256 前 8 位
"""

from __future__ import annotations

import hashlib
import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from meetrec.paths import logs_dir

LOG_FILE = "meetrec.log"
MAX_BYTES = 1_000_000  # 1 MB
BACKUP_COUNT = 5
DEFAULT_LEVEL = logging.INFO

_SIMPLE_MASKS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(sk-[A-Za-z0-9_-]{16,})"), "***API_KEY***"),
    (re.compile(r"(AKIA[A-Z0-9]{16})"), "***AWS_KEY***"),
    (re.compile(r"(Bearer\s+[A-Za-z0-9_.-]{20,})"), "Bearer ***"),
    (re.compile(r"(Authorization\s*:\s*[^\n,]+)"), "Authorization: ***"),
    (
        re.compile(r'("(api_?key|token|secret)"\s*:\s*")[^"]*(")'),
        r"\1***\3",
    ),
)

_PROMPT_FIELDS = re.compile(
    r'"(prompt|content|system|messages)"\s*:\s*"([^"]{20,})"',
    re.IGNORECASE,
)


def _redact_prompt_value(m: re.Match[str]) -> str:
    """将 Prompt 正文替换为长度与哈希前缀。"""
    field = m.group(1)
    value = m.group(2)
    digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f'"{field}": "[{len(value)} chars, sha256:{digest}]"'


class RedactionFilter(logging.Filter):
    """全局日志脱敏过滤器，挂在所有 Handler 上（ADR-010）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(str(record.msg))
        args = record.args
        if args is not None:
            if isinstance(args, dict):
                record.args = {k: self._redact_value(v) for k, v in args.items()}
            elif isinstance(args, tuple):
                record.args = tuple(self._redact_value(a) for a in args)
            elif isinstance(args, str):
                record.args = self._redact(args)
        return True

    @staticmethod
    def _redact(text: str) -> str:
        for pattern, replacement in _SIMPLE_MASKS:
            text = pattern.sub(replacement, text)
        text = _PROMPT_FIELDS.sub(_redact_prompt_value, text)
        return text

    @staticmethod
    def _redact_value(value: object) -> object:
        if isinstance(value, str):
            return RedactionFilter._redact(value)
        return value


def setup_logging(level: int = DEFAULT_LEVEL, log_dir: Path | None = None) -> logging.Logger:
    """配置全局日志：文件（滚动 5x1 MB）+ 控制台，均挂脱敏 Filter。"""
    target_dir = log_dir or logs_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        filename=target_dir / LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(RedactionFilter())

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RedactionFilter())

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return root


def get_logger(name: str) -> logging.Logger:
    """获取带 meetrec. 前缀的 logger。"""
    return logging.getLogger(f"meetrec.{name}")
