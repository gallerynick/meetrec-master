"""Meeting 数据模型测试。"""

from __future__ import annotations

from meetrec.models import Meeting


def test_meeting_defaults():
    m = Meeting(id="test-123", title="测试会议", created_at="2026-01-01T10:00:00")
    assert m.id == "test-123"
    assert m.title == "测试会议"
    assert m.status == "created"
    assert m.transcript == ""
    assert m.summary == ""
    assert m.word_count == 0


def test_meeting_has_audio():
    m = Meeting(id="1", title="x", created_at="2026-01-01", audio_path="/tmp/a.wav")
    assert m.has_audio()
    assert not m.has_transcript()
    assert not m.has_corrected()
    assert not m.has_summary()


def test_meeting_has_transcript():
    m = Meeting(id="1", title="x", created_at="2026-01-01", transcript="hello")
    assert m.has_transcript()
    assert not m.has_corrected()


def test_meeting_has_corrected():
    m = Meeting(id="1", title="x", created_at="2026-01-01", corrected_transcript="hello")
    assert m.has_corrected()


def test_meeting_has_summary():
    m = Meeting(id="1", title="x", created_at="2026-01-01", summary="summary")
    assert m.has_summary()


def test_meeting_display_title():
    m = Meeting(id="1", title="产品评审", created_at="2026-01-01")
    assert m.display_title == "产品评审"

    m2 = Meeting(id="123456789012", title="", created_at="2026-01-01")
    assert m2.display_title == "123456789012"


def test_meeting_to_dict():
    m = Meeting(
        id="1",
        title="会议",
        created_at="2026-01-01",
        audio_path="/a.wav",
        transcript="转录",
        corrected_transcript="校对后",
        summary="纪要",
        hotwords=["热词1", "热词2"],
        status="exported",
        duration=120.5,
        word_count=100,
        provider="openai",
        model_size="base",
    )
    d = m.to_dict()
    assert d["id"] == "1"
    assert d["title"] == "会议"
    assert d["transcript"] == "转录"
    assert d["corrected_transcript"] == "校对后"
    assert d["summary"] == "纪要"
    assert d["hotwords"] == ["热词1", "热词2"]
    assert d["status"] == "exported"
    assert d["duration"] == 120.5
    assert d["word_count"] == 100
    assert d["provider"] == "openai"
    assert d["model_size"] == "base"


def test_meeting_from_dict():
    data = {
        "id": "2",
        "title": "测试",
        "created_at": "2026-01-02",
        "status": "transcribed",
        "transcript": "文本",
        "duration": 30.0,
    }
    m = Meeting.from_dict(data)
    assert m.id == "2"
    assert m.title == "测试"
    assert m.status == "transcribed"
    assert m.transcript == "文本"
    assert m.duration == 30.0


def test_meeting_roundtrip():
    m = Meeting(id="3", title="往返", created_at="2026-01-03")
    m.audio_path = "/a.wav"
    m.transcript = "转录文本"
    m.hotwords = ["热词"]
    m.summary = "纪要内容"
    m.status = "exported"

    d = m.to_dict()
    m2 = Meeting.from_dict(d)

    assert m2.id == m.id
    assert m2.title == m.title
    assert m2.audio_path == m.audio_path
    assert m2.transcript == m.transcript
    assert m2.hotwords == m.hotwords
    assert m2.summary == m.summary
    assert m2.status == m.status
