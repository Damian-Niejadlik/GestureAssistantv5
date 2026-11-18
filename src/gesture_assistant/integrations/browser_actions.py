import webbrowser
from urllib.parse import urlsplit

from src.gesture_assistant.integrations.contracts import ActionSpec, ContextKind, unavailable
from src.gesture_assistant.integrations.native_backend import require_guard

ACTIONS = tuple(
    ActionSpec(
        f"browser.{name}",
        ContextKind.BROWSER,
        destructive=name == "close_tab",
        implemented=True,
        requires_target=name != "open_url",
    )
    for name in (
        "open_url",
        "new_tab",
        "close_tab",
        "next_tab",
        "previous_tab",
        "refresh_page",
        "go_back",
    )
)
DEFAULT_SHORTCUTS = {
    "browser.new_tab": "ctrl+t",
    "browser.close_tab": "ctrl+w",
    "browser.next_tab": "ctrl+tab",
    "browser.previous_tab": "ctrl+shift+tab",
    "browser.refresh_page": "ctrl+r",
    "browser.go_back": "alt+left",
}


def validate_url(value):
    if (
        not isinstance(value, str)
        or not value
        or any(c.isspace() or ord(c) < 32 or c == "\\" for c in value)
    ):
        raise ValueError("URL nie może być pusty ani zawierać spacji/znaków sterujących.")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Dozwolony wyłącznie HTTPS bez poświadczeń.")
    try:
        parts.hostname.encode("idna")
        port = parts.port
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Niepoprawny host lub port URL.") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Niepoprawny port URL.")
    return value


def open_url(url, guard):
    url = validate_url(url)
    require_guard(guard)
    if not webbrowser.open(url, new=2, autoraise=False):
        raise OSError("Przeglądarka nie przyjęła żądania otwarcia URL.")


def _send(name, keyboard, guard, shortcuts=None):
    action_id = f"browser.{name}"
    keyboard.hotkey(
        (shortcuts or {}).get(action_id, DEFAULT_SHORTCUTS[action_id]),
        guard,
        allow_reserved=name == "close_tab",
    )


def new_tab(keyboard, guard, shortcuts=None):
    _send("new_tab", keyboard, guard, shortcuts)


def close_tab(keyboard, guard, shortcuts=None):
    _send("close_tab", keyboard, guard, shortcuts)


def next_tab(keyboard, guard, shortcuts=None):
    _send("next_tab", keyboard, guard, shortcuts)


def previous_tab(keyboard, guard, shortcuts=None):
    _send("previous_tab", keyboard, guard, shortcuts)


def refresh_page(keyboard, guard, shortcuts=None):
    _send("refresh_page", keyboard, guard, shortcuts)


def go_back(keyboard, guard, shortcuts=None):
    _send("go_back", keyboard, guard, shortcuts)


execute = unavailable

