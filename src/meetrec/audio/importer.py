"""音频文件导入。

使用 PyAV 解码，支持 WAV/MP3/M4A/AAC/FLAC/OGG。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import av

from meetrec.errors import AudioError

__all__ = ["AudioImporter", "AudioInfo"]


@dataclass
class AudioInfo:
    """音频文件元数据。"""

    path: str
    duration: float
    sample_rate: int
    channels: int
    size_bytes: int
    format: str = ""


class AudioImporter:
    """音频文件导入器。"""

    SUPPORTED_EXT = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg")

    @classmethod
    def is_supported(cls, path: str | Path) -> bool:
        """检查文件扩展名是否支持。"""
        return Path(path).suffix.lower() in cls.SUPPORTED_EXT

    @classmethod
    def import_file(cls, path: str | Path) -> AudioInfo:
        """导入音频文件，返回元数据。"""
        path = Path(path)
        if not cls.is_supported(path):
            raise AudioError(message=f"不支持的格式：{path.suffix}")
        if not path.exists():
            raise AudioError(message=f"文件不存在：{path}")

        try:
            container = av.open(str(path))
            audio_stream = container.streams.audio[0]
            dur = (
                float(container.duration / av.time_base)
                if container.duration
                else 0.0
            )
            container.close()
        except Exception as e:
            raise AudioError(message=f"音频解码失败：{e}") from e

        return AudioInfo(
            path=str(path),
            duration=dur,
            sample_rate=audio_stream.rate or 16000,
            channels=audio_stream.channels or 1,
            size_bytes=path.stat().st_size,
            format=path.suffix.lower().lstrip("."),
        )
