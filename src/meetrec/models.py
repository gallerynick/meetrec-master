"""会议数据模型。

Meeting 是整个应用的核心数据结构，贯穿录音 → 转写 → 校正 → 纪要 → 导出全流程。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

__all__ = ["Meeting"]


@dataclass
class Meeting:
    """一次会议的数据模型。"""

    id: str
    title: str
    created_at: str  # ISO 8601
    audio_path: str | None = None
    transcript: str = ""
    corrected_transcript: str = ""
    summary: str = ""
    hotwords: list[str] = field(default_factory=list)
    status: str = "created"
    duration: float = 0.0
    word_count: int = 0
    provider: str = ""
    model_size: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Meeting:
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})

    @property
    def display_title(self) -> str:
        return self.title if self.title else self.id[:12]

    def has_audio(self) -> bool:
        return self.audio_path is not None

    def has_transcript(self) -> bool:
        return bool(self.transcript)

    def has_corrected(self) -> bool:
        return bool(self.corrected_transcript)

    def has_summary(self) -> bool:
        return bool(self.summary)
