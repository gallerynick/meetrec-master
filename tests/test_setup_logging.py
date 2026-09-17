"""setup_logging 与日志文件落盘测试。"""

from __future__ import annotations

import logging

from meetrec.log import get_logger, setup_logging


def test_setup_logging_writes_redacted_file(tmp_path):
    logger = setup_logging(log_dir=tmp_path)
    log = get_logger("test")
    log.info("使用密钥 sk-abcdefghijklmnopqrstuvwxyz123 完成调用")
    log.handlers[0].flush() if log.handlers else None

    log_file = tmp_path / "meetrec.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "sk-abcdefghijklmnopqrstuvwxyz123" not in content
    assert "***API_KEY***" in content
    logger.handlers.clear()


def test_setup_logging_is_idempotent(tmp_path):
    setup_logging(log_dir=tmp_path)
    setup_logging(log_dir=tmp_path)
    root = logging.getLogger()
    # 重复调用应清理旧 handler，避免累积
    assert len(root.handlers) == 2  # 文件 + 控制台
    root.handlers.clear()
