"""Markdown 导出。

将会议数据导出为结构化 Markdown 文件。
"""

from __future__ import annotations

from pathlib import Path

from meetrec.models import Meeting
from meetrec.paths import export_dir

__all__ = ["MarkdownExporter"]


class MarkdownExporter:
    """Markdown 导出器。"""

    def export(
        self, meeting: Meeting, output_dir: Path | None = None
    ) -> Path:
        """导出会议为 Markdown 文件，返回文件路径。"""
        out_dir = output_dir or export_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_title = meeting.display_title.replace(
            chr(47), chr(95)
        )  # / → _
        path = out_dir / f"{safe_title}.md"
        path.write_text(self.to_markdown(meeting), encoding="utf-8")
        return path

    def to_markdown(self, meeting: Meeting) -> str:
        """生成 Markdown 文本。"""
        nl = chr(10)
        parts: list[str] = [f"# {meeting.display_title}", ""]

        meta = [f"- **创建时间**: {meeting.created_at}"]
        if meeting.duration > 0:
            meta.append(f"- **录音时长**: {self._fmt_duration(meeting.duration)}")
        if meeting.model_size:
            meta.append(f"- **ASR 模型**: {meeting.model_size}")
        if meeting.provider:
            meta.append(f"- **AI 提供方**: {meeting.provider}")
        if meeting.word_count > 0:
            meta.append(f"- **转录字数**: {meeting.word_count}")
        parts.extend([*meta, ""])

        if meeting.transcript:
            parts.extend(["## 转录原文", "", meeting.transcript, ""])
        if meeting.corrected_transcript:
            parts.extend(
                ["## 校正后文本", "", meeting.corrected_transcript, ""]
            )
        if meeting.summary:
            parts.extend(["## AI 纪要", "", meeting.summary, ""])
        if meeting.hotwords:
            parts.append("## 热词")
            parts.append("")
            parts.extend(f"- {hw}" for hw in meeting.hotwords)
            parts.append("")

        return nl.join(parts)

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        if m > 0:
            return f"{m}分{s}秒"
        return f"{s}秒"
