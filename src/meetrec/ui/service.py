"""会议服务层。

协调所有后端模块（录音、转写、校正、纪要、导出），
为 UI 提供统一的同步 API。长耗时操作由 UI 层的 Worker 线程调用。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from meetrec.ai.providers import create_provider
from meetrec.ai.summarizer import Summarizer
from meetrec.asr.engine import ASREngine, TranscriptionResult
from meetrec.audio.importer import AudioImporter
from meetrec.audio.recorder import Recorder
from meetrec.errors import AudioError
from meetrec.export.markdown import MarkdownExporter
from meetrec.keywords.corrector import CorrectionResult, KeywordCorrector
from meetrec.meetings.store import MeetingStore
from meetrec.models import Meeting
from meetrec.paths import meetings_dir

__all__ = ["MeetingService"]


class MeetingService:
    """会议服务层：协调所有后端模块。"""

    def __init__(self) -> None:
        self.store = MeetingStore()
        self.recorder = Recorder()
        self.engine = ASREngine()
        self.exporter = MarkdownExporter()

    def create_meeting(self, title: str = "新会议") -> Meeting:
        return self.store.create(title)

    def list_meetings(self) -> list[Meeting]:
        return self.store.list()

    def get_meeting(self, meeting_id: str) -> Meeting | None:
        return self.store.get(meeting_id)

    def update_meeting(self, meeting: Meeting) -> None:
        self.store.save(meeting)

    def start_recording(
        self, meeting: Meeting, device_index: int | None = None
    ) -> None:
        self.recorder.start(device_index=device_index)
        meeting.status = "recording"
        self.store.save(meeting)

    def stop_recording(self, meeting: Meeting) -> Path:
        audio = self.recorder.stop()
        if audio.size == 0:
            raise AudioError(message="录音时长为零，无法保存")
        audio_dir = meetings_dir() / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        path = audio_dir / f"{meeting.id}.wav"
        Recorder.save_wav(audio, path, self.recorder.sample_rate)
        meeting.audio_path = str(path)
        meeting.duration = self.recorder.duration
        meeting.status = "recorded"
        self.store.save(meeting)
        return path

    def import_audio(self, meeting: Meeting, audio_path: str) -> None:
        info = AudioImporter.import_file(audio_path)
        meeting.audio_path = str(audio_path)
        meeting.duration = info.duration
        meeting.status = "recorded"
        self.store.save(meeting)

    def transcribe(
        self,
        meeting: Meeting,
        model_size: str,
        progress_cb: Callable[[str], None] | None = None,
    ) -> TranscriptionResult:
        if not meeting.audio_path:
            raise AudioError(message="未设置音频文件")
        meeting.status = "transcribing"
        self.store.save(meeting)
        self.engine.load_model(model_size)
        result = self.engine.transcribe(
            meeting.audio_path, progress_cb=progress_cb
        )
        meeting.transcript = result.text
        meeting.word_count = len(result.text)
        meeting.model_size = model_size
        meeting.status = "transcribed"
        self.store.save(meeting)
        return result

    def correct(
        self, meeting: Meeting, hotwords: list[str]
    ) -> CorrectionResult:
        if not hotwords:
            return CorrectionResult(text=meeting.transcript)
        meeting.status = "correcting"
        self.store.save(meeting)
        corrector = KeywordCorrector(hotwords)
        result = corrector.correct(meeting.transcript)
        meeting.corrected_transcript = result.text
        meeting.hotwords = hotwords
        meeting.status = "corrected"
        self.store.save(meeting)
        return result

    def summarize(
        self,
        meeting: Meeting,
        provider_name: str,
        api_key: str,
        instructions: str = "",
    ) -> str:
        meeting.status = "summarizing"
        self.store.save(meeting)
        provider = create_provider(provider_name, api_key)
        summarizer = Summarizer(provider)
        text = meeting.corrected_transcript or meeting.transcript
        summary = summarizer.generate(text, instructions, meeting.hotwords)
        meeting.summary = summary
        meeting.provider = provider_name
        meeting.status = "summarized"
        self.store.save(meeting)
        return summary

    def export(
        self, meeting: Meeting, output_dir: Path | None = None
    ) -> Path:
        meeting.status = "exported"
        self.store.save(meeting)
        return self.exporter.export(meeting, output_dir)
