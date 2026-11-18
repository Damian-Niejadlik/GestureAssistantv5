"""System media keys; the OS, not this module, selects the receiving media session."""

from src.gesture_assistant.integrations.contracts import ActionSpec, ContextKind, unavailable

ACTIONS = tuple(
    ActionSpec(f"media.{name}", ContextKind.MEDIA, implemented=True)
    for name in ("play_pause", "stop", "volume_up", "volume_down", "next_track", "previous_track")
)
DEFAULT_SHORTCUTS = {
    "media.play_pause": "media_play_pause",
    "media.stop": "media_stop",
    "media.volume_up": "volume_up",
    "media.volume_down": "volume_down",
    "media.next_track": "media_next_track",
    "media.previous_track": "media_previous_track",
}


def _send(name, keyboard, guard, shortcuts=None):
    action_id = f"media.{name}"
    value = (shortcuts or {}).get(action_id, DEFAULT_SHORTCUTS[action_id])
    return keyboard.hotkey(value, guard)


def play_pause(keyboard, guard, shortcuts=None):
    return _send("play_pause", keyboard, guard, shortcuts)


def stop(keyboard, guard, shortcuts=None):
    return _send("stop", keyboard, guard, shortcuts)


def volume_up(keyboard, guard, shortcuts=None):
    return _send("volume_up", keyboard, guard, shortcuts)


def volume_down(keyboard, guard, shortcuts=None):
    return _send("volume_down", keyboard, guard, shortcuts)


def next_track(keyboard, guard, shortcuts=None):
    return _send("next_track", keyboard, guard, shortcuts)


def previous_track(keyboard, guard, shortcuts=None):
    return _send("previous_track", keyboard, guard, shortcuts)


execute = unavailable

