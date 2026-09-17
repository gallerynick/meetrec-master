"""Worker QThread 测试。"""

from __future__ import annotations

from meetrec.ui.workers import Worker


def test_worker_success(qtbot):
    """Worker 成功执行并返回结果。"""
    progress_msgs: list[str] = []
    results: list[object] = []

    def work_fn(x: int, progress_cb=None):
        if progress_cb:
            progress_cb("50%")
        return x * 2

    w = Worker(work_fn, 5)
    w.progress.connect(progress_msgs.append)
    w.result_ready.connect(results.append)

    w.start()
    qtbot.waitUntil(lambda: len(results) > 0, timeout=5000)
    w.wait(2000)

    assert results == [10]
    assert progress_msgs == ["50%"]


def test_worker_error(qtbot):
    """Worker 异常时发出 error 信号。"""
    errors: list[str] = []

    def fail_fn():
        raise ValueError("测试错误")

    w = Worker(fail_fn)
    w.error.connect(errors.append)

    w.start()
    qtbot.waitUntil(lambda: len(errors) > 0, timeout=5000)
    w.wait(2000)

    assert len(errors) == 1
    assert "ValueError" in errors[0]
    assert "测试错误" in errors[0]


def test_worker_no_progress_cb(qtbot):
    """函数不接受 progress_cb 时不注入。"""
    results: list[object] = []

    def simple_fn(x):
        return x + 1

    w = Worker(simple_fn, 41)
    w.result_ready.connect(results.append)

    w.start()
    qtbot.waitUntil(lambda: len(results) > 0, timeout=5000)
    w.wait(2000)

    assert results == [42]
