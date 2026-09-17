"""__main__.py 命令行入口测试。"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from meetrec.__main__ import main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "meetrec 0.1.0" in out


def test_info_flag():
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main(["--info"]) == 0
    out = buf.getvalue()
    assert "MeetRec Master" in out
    assert "Data dir:" in out


def test_no_gui_flag():
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main(["--no-gui"]) == 0
    assert "初始化完成" in buf.getvalue()
