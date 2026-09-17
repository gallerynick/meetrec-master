"""音频录音器。

使用 sounddevice 流式采集，16kHz mono float32。
支持实时电平计算（RMS 到 dBFS）和 WAV 保存。
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from meetrec.errors import AudioError

__all__ = ["Recorder"]


class Recorder:
    """流式音频录音器。"""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = "float32",
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._dtype = dtype
        self._stream = None
        self._buffer: list[np.ndarray] = []
        self._level = 0.0
        self._recording = False

    def start(self, device_index: int | None = None) -> None:
        """开始录音。"""
        if self._recording:
            return
        try:
            self._buffer = []
            self._level = 0.0
            blocksize = int(self._sample_rate * 0.05)  # 50ms blocks
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype=self._dtype,
                blocksize=blocksize,
                device=device_index,
                callback=self._callback,
            )
            self._stream.start()
            self._recording = True
        except Exception as e:
            raise AudioError(message=f"录音启动失败：{e}") from e

    def stop(self) -> np.ndarray:
        """停止录音，返回 float32 mono 音频数据。"""
        if not self._recording:
            return np.array([], dtype=self._dtype)
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
            self._recording = False
        if self._buffer:
            return np.concatenate(self._buffer)
        return np.array([], dtype=self._dtype)

    def _callback(self, indata, frames, time_info, status) -> None:
        """录音回调（实时线程，保持轻量）。"""
        self._buffer.append(indata.copy())
        rms = float(np.sqrt(np.mean(indata ** 2))) if indata.size > 0 else 0.0
        self._level = rms

    @property
    def duration(self) -> float:
        """当前录音时长（秒）。"""
        return sum(b.shape[0] for b in self._buffer) / self._sample_rate

    @property
    def level(self) -> float:
        """当前 RMS 电平（0 到 1）。"""
        return self._level

    @property
    def level_db(self) -> float:
        """当前 dBFS 电平（-60 到 0）。"""
        if self._level <= 0:
            return -60.0
        return max(-60.0, 20.0 * np.log10(self._level))

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @staticmethod
    def save_wav(
        audio: np.ndarray, path: str | Path, sample_rate: int = 16000
    ) -> Path:
        """保存 float32 音频为 16-bit WAV 文件。"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if audio.ndim > 1:
            audio = audio[:, 0]
        audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        with wave.open(str(path), "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sample_rate)
            f.writeframes(audio_int16.tobytes())
        return path

    @staticmethod
    def input_devices() -> list[dict]:
        """列出可用的音频输入设备。"""
        try:
            devices = sd.query_devices()
            return [d for d in devices if d.get("max_input_channels", 0) > 0]
        except Exception:
            return []
