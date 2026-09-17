"""log.py 脱敏 Filter 单元测试。"""

from __future__ import annotations

import logging

from meetrec.log import RedactionFilter


def _redact(text: str) -> str:
    return RedactionFilter._redact(text)


def test_openai_key_redacted():
    assert "sk-abc" not in _redact("使用 sk-abcdefghijklmnopqrstuvwxyz123 调用")


def test_aws_key_redacted():
    assert "AKIA" not in _redact("凭证 AKIAABCDEFGHIJKLMNOP 已过期")


def test_bearer_token_redacted():
    out = _redact("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload")
    assert "eyJ" not in out
    assert "Authorization: ***" in out


def test_json_api_key_redacted():
    out = _redact('{"api_key": "sk-abcdefghijklmnop", "model": "gpt-4"}')
    assert "sk-abcdefghijklmnop" not in out


def test_prompt_body_replaced_with_hash():
    long_prompt = "请总结本次会议讨论的重点内容" * 10
    out = _redact(f'"prompt": "{long_prompt}"')
    assert long_prompt not in out
    assert "chars, sha256:" in out


def test_filter_handles_record_args():
    filter = RedactionFilter()
    record = logging.LogRecord(
        name="meetrec.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="key=%s",
        args=("sk-abcdefghijklmnopqrstuvwxyz",),
        exc_info=None,
    )
    assert filter.filter(record) is True
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in str(record.msg) + str(record.args)


def test_normal_text_unchanged():
    text = "今天的会议讨论了产品路线图"
    assert _redact(text) == text
