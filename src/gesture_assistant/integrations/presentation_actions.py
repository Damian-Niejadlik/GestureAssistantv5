"""PowerPoint shortcuts through the authorized keyboard backend."""

from src.gesture_assistant.integrations.contracts import ActionSpec, ContextKind, unavailable

ACTIONS = tuple(
    ActionSpec(f"presentation.{name}", ContextKind.PRESENTATION, implemented=True)
    for name in ("next_slide", "previous_slide", "start_presentation", "end_presentation")
)
DEFAULT_SHORTCUTS = {
    "presentation.next_slide": "right",
    "presentation.previous_slide": "left",
    "presentation.start_presentation": "f5",
    "presentation.end_presentation": "escape",
}


def _send(name, keyboard, guard, shortcuts=None):
    action_id = f"presentation.{name}"
    value = (shortcuts or {}).get(action_id, DEFAULT_SHORTCUTS[action_id])
    return keyboard.hotkey(value, guard)


def next_slide(keyboard, guard, shortcuts=None):
    return _send("next_slide", keyboard, guard, shortcuts)


def previous_slide(keyboard, guard, shortcuts=None):
    return _send("previous_slide", keyboard, guard, shortcuts)


def start_presentation(keyboard, guard, shortcuts=None):
    return _send("start_presentation", keyboard, guard, shortcuts)


def end_presentation(keyboard, guard, shortcuts=None):
    return _send("end_presentation", keyboard, guard, shortcuts)


execute = unavailable

