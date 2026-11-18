import os
import time
from dataclasses import dataclass
from pathlib import PureWindowsPath

from src.gesture_assistant.integrations.contracts import ContextKind

PROCESS_CONTEXTS = {
    "teams.exe": ContextKind.TEAMS,
    "ms-teams.exe": ContextKind.TEAMS,
    "chrome.exe": ContextKind.BROWSER,
    "msedge.exe": ContextKind.BROWSER,
    "msedgewebview2.exe": ContextKind.BROWSER,
    "firefox.exe": ContextKind.BROWSER,
    "powerpnt.exe": ContextKind.PRESENTATION,
    "vlc.exe": ContextKind.MEDIA,
    "spotify.exe": ContextKind.MEDIA,
    "wmplayer.exe": ContextKind.MEDIA,
    "explorer.exe": ContextKind.SYSTEM,
}
MODES = ("Auto", "Teams", "Browser", "Presentation", "Media", "System")


def clock_ms():
    return time.perf_counter_ns() // 1_000_000


@dataclass(frozen=True)
class Foreground:
    hwnd: int
    pid: int
    executable: str


@dataclass(frozen=True)
class ContextSnapshot:
    kind: ContextKind
    foreground: Foreground | None
    observed_ms: int
    mode: str

    @property
    def identity(self):
        return self.foreground

    @property
    def profile(self):
        return self.kind if self.mode == "Auto" else ContextKind(self.mode)

    @property
    def is_own_process(self):
        return self.foreground is not None and self.foreground.pid == os.getpid()

    @property
    def system_blocked(self):

        return self.kind in (ContextKind.UNKNOWN, ContextKind.TEAMS, ContextKind.BROWSER)


def read_windows_foreground():
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    import pygetwindow

    window = pygetwindow.getActiveWindow()
    hwnd = getattr(window, "_hWnd", None) if window is not None else None
    if not hwnd or hwnd != user.GetForegroundWindow():
        return None
    pid = wintypes.DWORD()
    if not user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)):
        return None
    handle = kernel.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        if hwnd != user.GetForegroundWindow():
            return None
        return Foreground(int(hwnd), pid.value, buffer.value)
    finally:
        kernel.CloseHandle(handle)


class ContextDetector:
    def __init__(self, reader=read_windows_foreground, clock=clock_ms):
        self.reader = reader
        self.clock = clock

    def detect(self, mode="Auto"):
        if mode not in MODES:
            raise ValueError("Nieznany tryb kontekstu.")
        try:
            foreground = self.reader()
        except (OSError, ImportError, AttributeError, NotImplementedError):
            foreground = None
        kind = ContextKind.UNKNOWN
        if (
            isinstance(foreground, Foreground)
            and type(foreground.hwnd) is int
            and foreground.hwnd > 0
            and type(foreground.pid) is int
            and foreground.pid > 0
            and isinstance(foreground.executable, str)
            and PureWindowsPath(foreground.executable).is_absolute()
            and PureWindowsPath(foreground.executable).suffix.lower() == ".exe"
            and not any(ord(c) < 32 for c in foreground.executable)
        ):
            name = PureWindowsPath(foreground.executable).name.lower()

            if foreground.pid != os.getpid():
                kind = PROCESS_CONTEXTS.get(name, ContextKind.SYSTEM)
        else:
            foreground = None
        return ContextSnapshot(kind, foreground, self.clock(), mode)

