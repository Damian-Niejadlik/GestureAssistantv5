"""Lazy native Windows operations. Importing this module performs no action."""

import ctypes
import io
import os
import uuid
from datetime import datetime
from pathlib import Path

from src.gesture_assistant.integrations.keyboard_actions import (
    MEDIA_VIRTUAL_KEYS,
    validate_shortcut,
)


class AuthorizationLost(PermissionError):
    """Foreground, PAUSED or tracking authorization changed."""


def require_guard(guard):
    if guard is None or not guard():
        raise AuthorizationLost("Autoryzacja akcji wygasła lub zmieniło się okno.")


def windows_dll(name):
    if os.name != "nt":
        raise OSError("Akcje natywne wymagają Windows.")
    return ctypes.WinDLL(name, use_last_error=True)


def send_virtual_keys(keys, guard):
    from ctypes import wintypes

    user = windows_dll("user32")
    ulong_ptr = ctypes.c_size_t

    class MouseInput(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ulong_ptr),
        ]

    class KeyboardInput(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ulong_ptr),
        ]

    class HardwareInput(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class InputUnion(ctypes.Union):
        _fields_ = [("mi", MouseInput), ("ki", KeyboardInput), ("hi", HardwareInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("data", InputUnion)]

    user.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int)
    user.SendInput.restype = wintypes.UINT
    user.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user.GetAsyncKeyState.restype = wintypes.SHORT

    if any(user.GetAsyncKeyState(key) & 0x8000 for key in {*keys, 0x10, 0x11, 0x12, 0x5B, 0x5C}):
        raise OSError("Zwolnij fizycznie wciśnięte klawisze przed akcją.")

    def packet(key, released=False):
        extended = key in (0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2E, 0x5B)
        extended = extended or 0xAD <= key <= 0xB3
        flags = (2 if released else 0) | (1 if extended else 0)
        return Input(1, InputUnion(ki=KeyboardInput(key, 0, flags, 0, 0)))

    sequence = [packet(key) for key in keys] + [packet(key, True) for key in reversed(keys)]
    array = (Input * len(sequence))(*sequence)
    require_guard(guard)
    count = user.SendInput(len(array), array, ctypes.sizeof(Input))
    if count != len(array):

        releases = (Input * len(keys))(*(packet(key, True) for key in reversed(keys)))
        user.SendInput(len(releases), releases, ctypes.sizeof(Input))
        raise OSError(ctypes.get_last_error(), "SendInput nie wstawił całego skrótu (np. UIPI).")


class WindowsBackend:
    def __init__(self):
        self._screenshot_options = (Path.home() / "GestureAssistant" / "Screenshots", False, 0)

    def configure_screenshot(self, folder, copy_image, owner_hwnd):
        self._screenshot_options = (Path(folder), bool(copy_image), int(owner_hwnd))

    def hotkey(self, value, guard, allow_reserved=False):
        keys = validate_shortcut(value, allow_reserved)
        vk = {
            "ctrl": 0x11,
            "shift": 0x10,
            "alt": 0x12,
            "win": 0x5B,
            "enter": 0x0D,
            "escape": 0x1B,
            "space": 0x20,
            "tab": 0x09,
            "left": 0x25,
            "up": 0x26,
            "right": 0x27,
            "down": 0x28,
            "delete": 0x2E,
        }
        letters = "abcdefghijklmnopqrstuvwxyz0123456789"
        vk.update({letter: ord(letter.upper()) for letter in letters})
        vk.update({f"f{i}": 0x6F + i for i in range(1, 13)})
        vk.update({"pageup": 0x21, "pagedown": 0x22, "home": 0x24, "end": 0x23, "backspace": 0x08})
        vk.update(MEDIA_VIRTUAL_KEYS)
        send_virtual_keys([vk[key] for key in keys], guard)

    def toggle_system_mute(self, guard):
        send_virtual_keys([0xAD], guard)

    def lock_screen(self, guard):
        user = windows_dll("user32")
        user.LockWorkStation.argtypes = ()
        user.LockWorkStation.restype = ctypes.c_int
        require_guard(guard)
        if not user.LockWorkStation():
            raise ctypes.WinError(ctypes.get_last_error())

    def sleep_computer(self, guard):
        from ctypes import wintypes

        kernel = windows_dll("kernel32")
        advapi = windows_dll("advapi32")
        power = windows_dll("powrprof")

        class Luid(ctypes.Structure):
            _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

        class LuidAttributes(ctypes.Structure):
            _fields_ = [("Luid", Luid), ("Attributes", wintypes.DWORD)]

        class TokenPrivileges(ctypes.Structure):
            _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LuidAttributes * 1)]

        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        advapi.OpenProcessToken.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        )
        advapi.OpenProcessToken.restype = wintypes.BOOL
        advapi.LookupPrivilegeValueW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.POINTER(Luid),
        )
        advapi.LookupPrivilegeValueW.restype = wintypes.BOOL
        advapi.AdjustTokenPrivileges.argtypes = (
            wintypes.HANDLE,
            wintypes.BOOL,
            ctypes.POINTER(TokenPrivileges),
            wintypes.DWORD,
            ctypes.POINTER(TokenPrivileges),
            ctypes.POINTER(wintypes.DWORD),
        )
        advapi.AdjustTokenPrivileges.restype = wintypes.BOOL
        power.SetSuspendState.argtypes = (ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte)
        power.SetSuspendState.restype = ctypes.c_ubyte
        token = wintypes.HANDLE()
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x28, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        previous = TokenPrivileges()
        returned = wintypes.DWORD()
        adjusted = False
        try:
            luid = Luid()
            if not advapi.LookupPrivilegeValueW(None, "SeShutdownPrivilege", ctypes.byref(luid)):
                raise ctypes.WinError(ctypes.get_last_error())
            desired = TokenPrivileges(1, (LuidAttributes * 1)(LuidAttributes(luid, 2)))
            ctypes.set_last_error(0)
            if not advapi.AdjustTokenPrivileges(
                token,
                False,
                ctypes.byref(desired),
                ctypes.sizeof(previous),
                ctypes.byref(previous),
                ctypes.byref(returned),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            adjusted = True
            if ctypes.get_last_error() == 1300:
                raise PermissionError("Proces nie ma SeShutdownPrivilege.")
            require_guard(guard)
            if not power.SetSuspendState(False, False, False):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            if adjusted:
                advapi.AdjustTokenPrivileges(token, False, ctypes.byref(previous), 0, None, None)
            kernel.CloseHandle(token)

    def screenshot(self, guard):
        from PIL import ImageGrab

        if os.name != "nt":
            raise OSError("Zrzut ekranu tej integracji wymaga Windows.")
        require_guard(guard)
        folder, copy_image, owner_hwnd = self._screenshot_options
        folder.mkdir(parents=True, exist_ok=True)
        name = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex + ".png"
        destination = folder / name
        temporary = destination.with_suffix(".part")
        require_guard(guard)
        image = ImageGrab.grab(all_screens=True)
        try:
            require_guard(guard)
            image.save(temporary, format="PNG")
            require_guard(guard)
            os.replace(temporary, destination)
            if copy_image:
                try:
                    _copy_dib_to_clipboard(image, owner_hwnd, guard)
                except (OSError, ValueError) as exc:
                    return f"Zapisano: {destination}; nie skopiowano do schowka: {exc}"
        finally:
            image.close()
            temporary.unlink(missing_ok=True)
        return destination


def _copy_dib_to_clipboard(image, owner_hwnd, guard):
    from ctypes import wintypes

    if not owner_hwnd:
        raise ValueError("Brak okna właściciela schowka.")
    with image.convert("RGB") as rgb, io.BytesIO() as buffer:
        rgb.save(buffer, format="BMP")
        dib = buffer.getvalue()[14:]  # CF_DIB: nagłówek DIB i piksele, bez nagłówka pliku BMP.

    user = windows_dll("user32")
    kernel = windows_dll("kernel32")
    for dll, name, argtypes, restype in (
        (kernel, "GlobalAlloc", (wintypes.UINT, ctypes.c_size_t), wintypes.HGLOBAL),
        (kernel, "GlobalLock", (wintypes.HGLOBAL,), ctypes.c_void_p),
        (kernel, "GlobalUnlock", (wintypes.HGLOBAL,), wintypes.BOOL),
        (kernel, "GlobalFree", (wintypes.HGLOBAL,), wintypes.HGLOBAL),
        (user, "OpenClipboard", (wintypes.HWND,), wintypes.BOOL),
        (user, "EmptyClipboard", (), wintypes.BOOL),
        (user, "CloseClipboard", (), wintypes.BOOL),
        (user, "SetClipboardData", (wintypes.UINT, wintypes.HANDLE), wintypes.HANDLE),
    ):
        function = getattr(dll, name)
        function.argtypes = argtypes
        function.restype = restype

    data = kernel.GlobalAlloc(0x0002, len(dib))  # GMEM_MOVEABLE
    if not data:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        address = kernel.GlobalLock(data)
        if not address:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            ctypes.memmove(address, dib, len(dib))
        finally:
            kernel.GlobalUnlock(data)
        require_guard(guard)
        if not user.OpenClipboard(owner_hwnd):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            require_guard(guard)
            if not user.EmptyClipboard():
                raise ctypes.WinError(ctypes.get_last_error())
            if not user.SetClipboardData(8, data):  # CF_DIB
                raise ctypes.WinError(ctypes.get_last_error())
            data = None  # Od teraz pamięcią zarządza Windows.
        finally:
            user.CloseClipboard()
    finally:
        if data:
            kernel.GlobalFree(data)

