"""MeetingService 测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from meetrec.meetings.store import MeetingStore
from meetrec.ui.service import MeetingService


@pytest.fixture
def service(tmp_path) -> MeetingService:
    """Create a MeetingService with a temp store."""
    svc = MeetingService.__new__(MeetingService)
    svc.store = MeetingStore(base_dir=tmp_path)
    svc.recorder = MagicMock()
    svc.engine = MagicMock()
    svc.exporter = MagicMock()
    return svc


def test_create_meeting(service: MeetingService):
    m = service.create_meeting("测试")
    assert m.id is not None
    assert m.title == "测试"


def test_list_meetings(service: MeetingService):
    assert service.list_meetings() == []
    service.create_meeting("A")
    service.create_meeting("B")
    assert len(service.list_meetings()) == 2


def test_get_meeting(service: MeetingService):
    m = service.create_meeting("目标")
    found = service.get_meeting(m.id)
    assert found is not None
    assert found.title == "目标"


def test_get_meeting_not_found(service: MeetingService):
    assert service.get_meeting("nope") is None


def test_update_meeting(service: MeetingService):
    m = service.create_meeting("原始")
    m.title = "修改"
    service.update_meeting(m)
    reloaded = service.get_meeting(m.id)
    assert reloaded is not None
    assert reloaded.title == "修改"


def test_start_recording(service: MeetingService):
    m = service.create_meeting("录音测试")
    service.recorder.start = MagicMock()
    service.start_recording(m)
    assert m.status == "recording"
    assert service.recorder.start.called


def test_stop_recording(service: MeetingService):
    m = service.create_meeting("停止测试")
    m.audio_path = None
    # Simulate a stop that returns an AudioBuffer with size > 0
    fake_audio = MagicMock()
    fake_audio.size = 100
    service.recorder.stop = MagicMock(return_value=fake_audio)
    service.recorder.duration = 10.5
    service.recorder.sample_rate = 16000

    with patch("meetrec.audio.recorder.Recorder.save_wav"):
        service.stop_recording(m)
        assert m.audio_path is not None
        assert m.status == "recorded"
        assert m.duration == 10.5


def test_import_audio(service: MeetingService):
    m = service.create_meeting("导入测试")
    with patch("meetrec.audio.importer.AudioImporter.import_file") as mock_import:
        mock_import.return_value = MagicMock(duration=30.0)
        service.import_audio(m, "/tmp/test.wav")
        assert m.audio_path == "/tmp/test.wav"
        assert m.duration == 30.0
        assert m.status == "recorded"


def test_transcribe(service: MeetingService):
    m = service.create_meeting("转写测试")
    m.audio_path = "/tmp/audio.wav"
    result = MagicMock()
    result.text = "转录文本"
    result.duration = 5.0
    service.engine.transcribe = MagicMock(return_value=result)
    service.engine.load_model = MagicMock()

    service.transcribe(m, "base")
    assert m.transcript == "转录文本"
    assert m.model_size == "base"
    assert m.status == "transcribed"


def test_correct(service: MeetingService):
    m = service.create_meeting("校对测试")
    m.transcript = "原始文本"
    result = MagicMock()
    result.text = "校对后文本"
    result.corrections = []

    # Mock the corrector
    with patch("meetrec.ui.service.KeywordCorrector") as mock_corrector:
        instance = mock_corrector.return_value
        instance.correct.return_value = result
        service.correct(m, ["热词"])
        assert m.corrected_transcript == "校对后文本"
        assert m.hotwords == ["热词"]
        assert m.status == "corrected"


def test_summarize(service: MeetingService):
    m = service.create_meeting("纪要测试")
    m.corrected_transcript = "校对文本"
    m.hotwords = ["热词"]

    with patch("meetrec.ui.service.create_provider") as mock_create, \
            patch("meetrec.ui.service.Summarizer") as mock_summarizer:
        mock_provider = MagicMock()
        mock_create.return_value = mock_provider
        mock_summarizer = mock_summarizer.return_value
        mock_summarizer.generate.return_value = "AI 纪要"
        service.summarize(m, "openai", "test-key")
        assert m.summary == "AI 纪要"
        assert m.provider == "openai"
        assert m.status == "summarized"


def test_export(service: MeetingService):
    m = service.create_meeting("导出测试")
    m.transcript = "文本"
    fake_path = MagicMock()
    fake_path.__str__ = lambda self: "/tmp/export.md"
    service.exporter.export = MagicMock(return_value=fake_path)

    service.export(m)
    assert m.status == "exported"
