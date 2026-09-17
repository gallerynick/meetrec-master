"""AI 纪要生成。

构建结构化 prompt，调用 AI 提供方生成会议纪要。
"""

from __future__ import annotations

from meetrec.ai.providers import AIProvider
from meetrec.errors import ProviderError

__all__ = ["Summarizer"]


class Summarizer:
    """AI 纪要生成器。"""

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def generate(
        self,
        transcript: str,
        instructions: str = "",
        hotwords: list[str] | None = None,
    ) -> str:
        """生成会议纪要。"""
        if not transcript.strip():
            raise ProviderError(message="转录文本为空，无法生成纪要")
        prompt = self._build_prompt(transcript, instructions, hotwords)
        return self._provider.summarize(prompt)

    @staticmethod
    def _build_prompt(
        transcript: str,
        instructions: str = "",
        hotwords: list[str] | None = None,
    ) -> str:
        nl = chr(10)
        parts = [
            "你是一个专业的会议纪要助手。",
            "请将以下会议转录文本总结为结构化纪要。",
            "",
            "要求：",
            "1. 会议主题（一句话概括）",
            "2. 关键讨论点（按重要性排序）",
            "3. 决定事项（如有）",
            "4. 待办任务（负责人、截止日期，如有）",
            "",
        ]
        if hotwords:
            parts.append("注意以下专有名词，请保持原文不修改：")
            parts.append(chr(126).join(hotwords))
            parts.append("")
        if instructions:
            parts.append(f"额外要求：{instructions}")
            parts.append("")
        parts.append("转录文本：")
        parts.append(transcript)
        return nl.join(parts)
