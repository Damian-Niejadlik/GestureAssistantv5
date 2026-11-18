from src.gesture_assistant.integrations.keyboard_actions import validate_shortcut
from src.gesture_assistant.integrations.native_backend import require_guard


class FakeKeyboard:
    """Records validated requests, never calls SendInput or any OS function."""

    def __init__(self):
        self.calls = []

    def hotkey(self, value, guard, allow_reserved=False):
        keys = validate_shortcut(value, allow_reserved)
        require_guard(guard)
        self.calls.append((value, keys, allow_reserved))

