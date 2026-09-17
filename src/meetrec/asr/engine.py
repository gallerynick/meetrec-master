"""faster-whisper ASR 引擎。

模型从 hf-mirror.com 下载（HF_ENDPOINT + HF_HUB_DISABLE_XET）。
transcribe() 返回 (segments_generator, info) 元组，需解包。
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from meetrec.errors import ASRError, ModelDownloadError

__all__ = ["ASREngine", "Segment", "TranscriptionResult"]


@dataclass
class Segment:
    """转写片段。"""

    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    """转写结果。"""

    text: str
    segments: list[Segment]
    language: str
    duration: float


class ASREngine:
    """faster-whisper ASR 引擎。"""

    MODEL_SIZES: ClassVar[dict[str, str]] = {
        "tiny": "39M 参数 / 75MB / MIT",
        "base": "74M 参数 / 145MB / MIT",
        "small": "244M 参数 / 484MB / MIT",
        "medium": "769M 参数 / 1.5GB / MIT",
        "large-v3-turbo": "809M 参数 / 1.6GB / MIT",
        "large-v3": "1550M 参数 / 3.1GB / MIT",
    }

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model = None
        self._model_loaded = False

    @staticmethod
    def _set_hf_env() -> None:
        """设置 HuggingFace 镜像环境变量。"""
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

    @staticmethod
    def is_downloaded(size: str) -> bool:
        """检查模型是否已缓存。"""
        ASREngine._set_hf_env()
        try:
            from faster_whisper import WhisperModel

            m = WhisperModel(
                size, device="cpu", compute_type="int8", local_files_only=True
            )
            del m
            return True
        except Exception:
            return False

    def load_model(self, model_size: str | None = None) -> None:
        """加载模型（首次会自动下载）。"""
        if model_size:
            self._model_size = model_size
        self._set_hf_env()
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            self._model_loaded = True
        except Exception as e:
            raise ModelDownloadError(
                message=f"模型加载失败（{self._model_size}）：{e}"
            ) from e

    def transcribe(
        self,
        audio_path: str,
        language: str = "zh",
        initial_prompt: str | None = None,
        progress_cb: Callable[[str], None] | None = None,
    ) -> TranscriptionResult:
        """转写音频文件。"""
        if not self._model_loaded:
            self.load_model()
        if self._model is None:
            raise ASRError(message="模型未加载")

        try:
            result = self._model.transcribe(
                audio_path,
                language=language,
                beam_size=5,
                initial_prompt=initial_prompt,
            )
            # faster-whisper 1.2.1 返回 (segments_generator, info) 元组
            if isinstance(result, tuple):
                segments_gen, info = result
            else:
                segments_gen, info = result, None
        except Exception as e:
            raise ASRError(message=f"转写失败：{e}") from e

        seg_list: list[Segment] = []
        full_text = ""
        total_dur = info.duration if info else 0.0

        for seg in segments_gen:
            seg_list.append(
                Segment(start=seg.start, end=seg.end, text=seg.text.strip())
            )
            full_text += seg.text
            if progress_cb:
                prog = (
                    f"正在转写... {seg.end:.1f}s / {total_dur:.1f}s"
                    if total_dur
                    else f"正在转写... {seg.end:.1f}s"
                )
                progress_cb(prog)

        return TranscriptionResult(
            text=full_text.strip(),
            segments=seg_list,
            language=info.language if info else language,
            duration=total_dur,
        )

    @classmethod
    def available_models(cls) -> list[dict]:
        """列出可用模型及下载状态。"""
        return [
            {
                "size": size,
                "info": info,
                "downloaded": cls.is_downloaded(size),
            }
            for size, info in cls.MODEL_SIZES.items()
        ]
