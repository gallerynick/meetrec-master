"""会议持久化（JSON 文件）。

每个会议一个 JSON 文件，存储在 meetings_dir() 下。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from meetrec.models import Meeting
from meetrec.paths import meetings_dir

__all__ = ["MeetingStore"]


class MeetingStore:
    """会议 JSON 持久化。"""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._dir = base_dir or meetings_dir()
        self._dir.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[Meeting]:
        """列出所有会议，按创建时间倒序。"""
        meetings: list[Meeting] = []
        for f in self._dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                meetings.append(Meeting.from_dict(data))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
        meetings.sort(key=lambda m: m.created_at, reverse=True)
        return meetings

    def get(self, meeting_id: str) -> Meeting | None:
        path = self._dir / f"{meeting_id}.json"
        if not path.exists():
            return None
        try:
            return Meeting.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    def save(self, meeting: Meeting) -> None:
        path = self._dir / f"{meeting.id}.json"
        path.write_text(
            json.dumps(meeting.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def create(self, title: str = "新会议") -> Meeting:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:6]
        meeting = Meeting(
            id=f"{ts}_{uid}",
            title=title,
            created_at=datetime.now().isoformat(),
        )
        self.save(meeting)
        return meeting

    def delete(self, meeting_id: str) -> bool:
        path = self._dir / f"{meeting_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False
