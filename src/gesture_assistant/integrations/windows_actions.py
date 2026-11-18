from pathlib import Path

from src.gesture_assistant.integrations.contracts import ActionSpec, ContextKind, unavailable

ACTIONS = (
    ActionSpec("system.lock", ContextKind.SYSTEM, implemented=True),
    ActionSpec("sleep_computer", ContextKind.SYSTEM, destructive=True, implemented=True),
    ActionSpec("system.launch_application", ContextKind.SYSTEM),
    ActionSpec("system.toggle_mute", ContextKind.SYSTEM, implemented=True),
    ActionSpec("system.take_screenshot", ContextKind.SYSTEM, implemented=True),
    ActionSpec(
        "system.close_active_window",
        ContextKind.SYSTEM,
        destructive=True,
        implemented=True,
    ),
    ActionSpec("system.switch_virtual_desktop", ContextKind.SYSTEM, implemented=True),
)


def validate_application_path(value: str) -> Path:
    if (
        not isinstance(value, str)
        or not value
        or any(c in value for c in ('"', "\n", "\r", "\x00"))
    ):
        raise ValueError("Niepoprawna ścieżka aplikacji.")
    path = Path(value)
    if not path.is_absolute() or path.suffix.lower() != ".exe" or not path.is_file():
        raise ValueError("Wymagany istniejący bezwzględny plik .exe, bez argumentów.")
    if path.is_symlink():
        raise ValueError("Dowiązania nie są akceptowane jako aplikacje.")
    return path.resolve(strict=True)


execute = unavailable


def sleep_computer(backend, guard):
    return backend.sleep_computer(guard)


def toggle_system_mute(backend, guard):
    return backend.toggle_system_mute(guard)


def take_screenshot(backend, guard):
    return backend.screenshot(guard)


def lock_screen(backend, guard):
    return backend.lock_screen(guard)


def close_active_window(backend, guard):
    return backend.hotkey("alt+f4", guard, allow_reserved=True)


def switch_virtual_desktop(backend, guard, direction="right"):
    if direction not in ("left", "right"):
        raise ValueError("Kierunek pulpitu musi być left lub right.")
    return backend.hotkey(f"win+ctrl+{direction}", guard)

