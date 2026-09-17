"""MeetingStore 测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from meetrec.meetings.store import MeetingStore


@pytest.fixture
def tmp_store(tmp_path: Path) -> MeetingStore:
    return MeetingStore(base_dir=tmp_path)


def test_create_meeting(tmp_store: MeetingStore):
    m = tmp_store.create("测试会议")
    assert m.id is not None
    assert m.title == "测试会议"
    assert m.status == "created"
    assert m.created_at is not None


def test_list_meetings_empty(tmp_store: MeetingStore):
    assert tmp_store.list() == []


def test_list_meetings(tmp_store: MeetingStore):
    tmp_store.create("会议1")
    tmp_store.create("会议2")
    meetings = tmp_store.list()
    assert len(meetings) == 2
    titles = {m.title for m in meetings}
    assert titles == {"会议1", "会议2"}


def test_get_meeting(tmp_store: MeetingStore):
    m = tmp_store.create("目标会议")
    found = tmp_store.get(m.id)
    assert found is not None
    assert found.id == m.id
    assert found.title == "目标会议"


def test_get_meeting_not_found(tmp_store: MeetingStore):
    assert tmp_store.get("nonexistent") is None


def test_save_meeting(tmp_store: MeetingStore):
    m = tmp_store.create("原始")
    m.title = "修改后"
    m.transcript = "转录文本"
    tmp_store.save(m)

    reloaded = tmp_store.get(m.id)
    assert reloaded is not None
    assert reloaded.title == "修改后"
    assert reloaded.transcript == "转录文本"


def test_delete_meeting(tmp_store: MeetingStore):
    m = tmp_store.create("待删除")
    tmp_store.delete(m.id)
    assert tmp_store.get(m.id) is None
    assert len(tmp_store.list()) == 0


def test_delete_nonexistent(tmp_store: MeetingStore):
    # Should not raise
    tmp_store.delete("nonexistent")


def test_meeting_persistence(tmp_path: Path):
    """验证会议持久化到磁盘。"""
    store1 = MeetingStore(base_dir=tmp_path)
    m = store1.create("持久化测试")
    m.transcript = "你好世界"
    store1.save(m)

    # New store instance should see the data
    store2 = MeetingStore(base_dir=tmp_path)
    meetings = store2.list()
    assert len(meetings) == 1
    assert meetings[0].transcript == "你好世界"
