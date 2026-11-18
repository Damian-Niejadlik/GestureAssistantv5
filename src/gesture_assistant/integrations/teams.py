from src.gesture_assistant.integrations.contracts import ActionSpec, ContextKind, unavailable

ACTIONS = (
    ActionSpec("teams.toggle_mute", ContextKind.TEAMS, implemented=True),
    ActionSpec("teams.toggle_raise_hand", ContextKind.TEAMS, implemented=True),
    ActionSpec("teams.toggle_camera", ContextKind.TEAMS, implemented=True),
    ActionSpec("teams.reaction_like", ContextKind.TEAMS, implemented=True),
    ActionSpec("teams.reaction_applause", ContextKind.TEAMS, implemented=True),
    ActionSpec("teams.leave_meeting", ContextKind.TEAMS, destructive=True, implemented=True),
)
DEFAULT_SHORTCUTS = {
    "teams.toggle_mute": "ctrl+shift+m",
    "teams.toggle_raise_hand": "ctrl+shift+k",
    "teams.toggle_camera": "ctrl+shift+o",
    "teams.leave_meeting": "ctrl+shift+h",
}


def _send(action_id, keyboard, guard, shortcuts=None):
    shortcut = (shortcuts or {}).get(action_id, DEFAULT_SHORTCUTS.get(action_id))
    if not shortcut:
        raise ValueError(
            f"{action_id}: brak uniwersalnego skrótu. Skonfiguruj skrót obsługiwany przez Teams."
        )
    keyboard.hotkey(shortcut, guard, allow_reserved=action_id == "teams.leave_meeting")


def toggle_mute(keyboard, guard, shortcuts=None):
    _send("teams.toggle_mute", keyboard, guard, shortcuts)


def toggle_raise_hand(keyboard, guard, shortcuts=None):
    _send("teams.toggle_raise_hand", keyboard, guard, shortcuts)


def toggle_camera(keyboard, guard, shortcuts=None):
    _send("teams.toggle_camera", keyboard, guard, shortcuts)


def reaction_like(keyboard, guard, shortcuts=None):
    _send("teams.reaction_like", keyboard, guard, shortcuts)


def reaction_applause(keyboard, guard, shortcuts=None):
    _send("teams.reaction_applause", keyboard, guard, shortcuts)


def leave_meeting(keyboard, guard, shortcuts=None):
    _send("teams.leave_meeting", keyboard, guard, shortcuts)


execute = unavailable

