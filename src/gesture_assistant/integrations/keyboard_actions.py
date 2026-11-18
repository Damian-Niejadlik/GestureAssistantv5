
MEDIA_VIRTUAL_KEYS = {
    "volume_down": 0xAE,
    "volume_up": 0xAF,
    "media_next_track": 0xB0,
    "media_previous_track": 0xB1,
    "media_stop": 0xB2,
    "media_play_pause": 0xB3,
}

ALLOWED_MODIFIERS = frozenset({"ctrl", "alt", "shift", "win"})
ALLOWED_KEYS = frozenset(
    list("abcdefghijklmnopqrstuvwxyz0123456789")
    + ["enter", "escape", "space", "tab", "left", "right", "up", "down", "delete"]
    + ["pageup", "pagedown", "home", "end", "backspace"]
    + list(MEDIA_VIRTUAL_KEYS)
    + [f"f{i}" for i in range(1, 13)]
)
RESERVED = (
    frozenset({"ctrl", "alt", "delete"}),
    frozenset({"win", "l"}),
    frozenset({"alt", "f4"}),
    frozenset({"ctrl", "shift", "h"}),
    frozenset({"ctrl", "w"}),
    frozenset({"ctrl", "shift", "w"}),
)


def validate_shortcut(value: str, allow_reserved=False) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise ValueError("Skrót musi być tekstem.")
    keys = tuple(part.strip().lower() for part in value.split("+"))
    if not 1 <= len(keys) <= 4 or len(set(keys)) != len(keys):
        raise ValueError("Skrót wymaga 1–4 unikalnych klawiszy.")
    if keys[-1] not in ALLOWED_KEYS or any(k not in ALLOWED_MODIFIERS for k in keys[:-1]):
        raise ValueError("Niepoprawny klawisz lub modyfikator.")
    if frozenset(keys) == RESERVED[0] or (not allow_reserved and frozenset(keys) in RESERVED):
        raise ValueError("Zastrzeżony skrót wymaga akcji destrukcyjnej.")
    return keys


def send_shortcut(value, guard, allow_reserved=False):
    from src.gesture_assistant.integrations.native_backend import WindowsBackend

    return WindowsBackend().hotkey(value, guard, allow_reserved=allow_reserved)


def validate_action_shortcut(action_id, value):
    from src.gesture_assistant.integrations import ACTION_CATALOG
    from src.gesture_assistant.integrations.contracts import ContextKind

    action = ACTION_CATALOG.get(action_id)
    keys = validate_shortcut(value, allow_reserved=bool(action and action.destructive))
    if keys[-1] in MEDIA_VIRTUAL_KEYS:
        if action is None or action.context != ContextKind.MEDIA:
            raise ValueError("Klawisze multimedialne są dozwolone tylko dla akcji Media.")
        if len(keys) != 1:
            raise ValueError("Globalny klawisz multimedialny nie przyjmuje modyfikatorów.")
    return keys

