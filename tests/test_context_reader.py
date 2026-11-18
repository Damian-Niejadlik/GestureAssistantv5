import ctypes
import sys
from types import SimpleNamespace

import pytest

from src.gesture_assistant.core import context_detector


class FakeFunction:
    def __init__(self, function):
        self.function = function

    def __call__(self, *args):
        return self.function(*args)


@pytest.mark.parametrize(
    "query_ok, changed, own",
    [
        (True, False, False),
        (False, False, False),
        (True, True, False),
        (True, False, True),
    ],
)
def test_pygetwindow_reader_closes_process_handle(monkeypatch, query_ok, changed, own):
    from ctypes import wintypes

    closed = []
    foreground_calls = []

    def foreground():
        foreground_calls.append(1)
        return 12 if changed and len(foreground_calls) > 1 else 11

    def pid(hwnd, pointer):
        ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))[0] = 42
        return 1

    def query(handle, flags, buffer, size):
        buffer.value = "C:/Apps/POWERPNT.EXE"
        return query_ok

    user = SimpleNamespace(
        GetForegroundWindow=FakeFunction(foreground),
        GetWindowThreadProcessId=FakeFunction(pid),
    )
    kernel = SimpleNamespace(
        OpenProcess=FakeFunction(lambda *args: 7),
        QueryFullProcessImageNameW=FakeFunction(query),
        CloseHandle=FakeFunction(lambda handle: closed.append(handle) or 1),
    )
    monkeypatch.setattr(
        context_detector, "os", SimpleNamespace(name="nt", getpid=lambda: 42 if own else 999)
    )
    monkeypatch.setattr(
        ctypes, "WinDLL", lambda name, **kw: user if name == "user32" else kernel, raising=False
    )
    monkeypatch.setitem(
        sys.modules,
        "pygetwindow",
        SimpleNamespace(
            getActiveWindow=lambda: SimpleNamespace(_hWnd=11),
        ),
    )
    result = context_detector.read_windows_foreground()
    assert closed == [7]
    if query_ok and not changed:
        assert result.hwnd == 11 and result.pid == 42
        assert result.executable == "C:/Apps/POWERPNT.EXE"
    else:
        assert result is None

