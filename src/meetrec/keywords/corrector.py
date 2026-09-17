"""热词校正。

相似度公式：0.50 * pinyin_sim + 0.30 * edit_sim + 0.20 * len_sim
滑动窗口匹配：对每个热词，在文本中寻找最相似的子串。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pypinyin import Style, lazy_pinyin
from rapidfuzz import fuzz

__all__ = ["Correction", "CorrectionResult", "KeywordCorrector"]


@dataclass
class Correction:
    """单次校正记录。"""

    original: str
    corrected: str
    hotword: str
    position: int


@dataclass
class CorrectionResult:
    """校正结果。"""

    text: str
    corrections: list[Correction] = field(default_factory=list)


class KeywordCorrector:
    """热词校正器。"""

    def __init__(self, hotwords: list[str], threshold: float = 0.80) -> None:
        self._hotwords = list(dict.fromkeys(hotwords))  # 去重保序
        self._threshold = threshold

    @staticmethod
    def _pinyin_sim(a: str, b: str) -> float:
        """拼音相似度。"""
        pa = "".join(lazy_pinyin(a, style=Style.NORMAL))
        pb = "".join(lazy_pinyin(b, style=Style.NORMAL))
        return fuzz.ratio(pa, pb) / 100.0

    @staticmethod
    def _edit_sim(a: str, b: str) -> float:
        """编辑距离相似度。"""
        return fuzz.ratio(a, b) / 100.0

    @staticmethod
    def _len_sim(a: str, b: str) -> float:
        """长度相似度。"""
        max_len = max(len(a), len(b))
        if max_len == 0:
            return 1.0
        return 1.0 - abs(len(a) - len(b)) / max_len

    @classmethod
    def similarity(cls, a: str, b: str) -> float:
        """综合相似度：0.50 * pinyin + 0.30 * edit + 0.20 * len。"""
        if not a or not b:
            return 0.0
        return (
            0.50 * cls._pinyin_sim(a, b)
            + 0.30 * cls._edit_sim(a, b)
            + 0.20 * cls._len_sim(a, b)
        )

    def correct(self, text: str) -> CorrectionResult:
        """校正文本中的热词（滑动窗口匹配）。"""
        if not self._hotwords or not text:
            return CorrectionResult(text=text)

        result = text
        corrections: list[Correction] = []

        for hw in self._hotwords:
            if hw in result:
                continue  # 精确匹配，无需校正

            hw_len = len(hw)
            if hw_len == 0 or hw_len > len(result):
                continue

            best_pos = -1
            best_sim = 0.0

            for i in range(len(result) - hw_len + 1):
                candidate = result[i : i + hw_len]
                sim = self.similarity(candidate, hw)
                if sim > best_sim:
                    best_sim = sim
                    best_pos = i

            if best_pos >= 0 and best_sim >= self._threshold:
                original = result[best_pos : best_pos + hw_len]
                if original != hw:
                    result = (
                        result[:best_pos] + hw + result[best_pos + hw_len :]
                    )
                    corrections.append(
                        Correction(
                            original=original,
                            corrected=hw,
                            hotword=hw,
                            position=best_pos,
                        )
                    )

        return CorrectionResult(text=result, corrections=corrections)

    @property
    def hotwords(self) -> list[str]:
        return list(self._hotwords)
