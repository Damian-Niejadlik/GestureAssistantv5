import pytest

from src.gesture_assistant.config.schema import validate_config
from src.gesture_assistant.core.config_manager import defaults
from src.gesture_assistant.integrations import presentation_actions as presentation
from src.gesture_assistant.integrations.dispatcher import NativeDispatcher
from src.gesture_assistant.integrations.native_backend import AuthorizationLost
from tests.integration_samples import FakeKeyboard

CASES = [
    ("next_slide", "right"),
    ("previous_slide", "left"),
    ("start_presentation", "f5"),
    ("end_presentation", "escape"),
]


@pytest.mark.parametrize("name, expected", CASES)
def test_default_presentation_shortcut(name, expected):
    keyboard = FakeKeyboard()
    getattr(presentation, name)(keyboard, lambda: True)
    assert keyboard.calls == [(expected, (expected,), False)]


@pytest.mark.parametrize("name, expected", CASES)
def test_presentation_override(name, expected):
    keyboard = FakeKeyboard()
    action_id = f"presentation.{name}"
    getattr(presentation, name)(keyboard, lambda: True, {action_id: "ctrl+shift+p"})
    assert keyboard.calls[0][0] == "ctrl+shift+p"


@pytest.mark.parametrize("name, expected", CASES)
def test_no_authorization_no_keyboard(name, expected):
    keyboard = FakeKeyboard()
    with pytest.raises(AuthorizationLost):
        getattr(presentation, name)(keyboard, lambda: False)
    assert not keyboard.calls


def test_presentation_error_propagates_to_executor_boundary():
    class BrokenKeyboard:
        def hotkey(self, *args, **kwargs):
            raise OSError("controlled input failure")

    with pytest.raises(OSError, match="controlled input failure"):
        presentation.next_slide(BrokenKeyboard(), lambda: True)


def test_config_accepts_presentation_shortcuts_and_rejects_destructive_override():
    config = defaults()
    config["targets"]["shortcuts"]["presentation.next_slide"] = "pagedown"
    assert validate_config(config)["targets"]["shortcuts"]["presentation.next_slide"] == "pagedown"
    config["targets"]["shortcuts"]["presentation.next_slide"] = "alt+f4"
    with pytest.raises(ValueError):
        NativeDispatcher(config, FakeKeyboard())

