import pytest

from src.gesture_assistant.config.schema import validate_config
from src.gesture_assistant.core.config_manager import defaults
from src.gesture_assistant.integrations import media_actions as media
from src.gesture_assistant.integrations.keyboard_actions import (
    MEDIA_VIRTUAL_KEYS,
    validate_action_shortcut,
)
from src.gesture_assistant.integrations.native_backend import AuthorizationLost, WindowsBackend
from tests.integration_samples import FakeKeyboard

CASES = [
    ("play_pause", "media_play_pause", 0xB3),
    ("stop", "media_stop", 0xB2),
    ("volume_up", "volume_up", 0xAF),
    ("volume_down", "volume_down", 0xAE),
    ("next_track", "media_next_track", 0xB0),
    ("previous_track", "media_previous_track", 0xB1),
]


@pytest.mark.parametrize("name, key, vk", CASES)
def test_media_default_and_vk(name, key, vk):
    keyboard = FakeKeyboard()
    getattr(media, name)(keyboard, lambda: True)
    assert keyboard.calls == [(key, (key,), False)]
    assert MEDIA_VIRTUAL_KEYS[key] == vk


@pytest.mark.parametrize("name, key, vk", CASES)
def test_media_overrides(name, key, vk):
    keyboard = FakeKeyboard()
    action_id = f"media.{name}"
    getattr(media, name)(keyboard, lambda: True, {action_id: "ctrl+shift+p"})
    assert keyboard.calls[0][0] == "ctrl+shift+p"


@pytest.mark.parametrize("name, key, vk", CASES)
def test_media_guard_blocks(name, key, vk):
    keyboard = FakeKeyboard()
    with pytest.raises(AuthorizationLost):
        getattr(media, name)(keyboard, lambda: False)
    assert not keyboard.calls


@pytest.mark.parametrize("name, key, vk", CASES)
def test_backend_mapping_without_native_execution(monkeypatch, name, key, vk):
    from src.gesture_assistant.integrations import native_backend

    calls = []

    def fake_send(keys, guard):
        assert guard()
        calls.append(keys)

    monkeypatch.setattr(native_backend, "send_virtual_keys", fake_send)
    WindowsBackend().hotkey(key, lambda: True)
    assert calls == [[vk]]


def test_media_keys_cannot_hide_inside_teams_profile():
    config = defaults()
    config["targets"]["shortcuts"]["teams.toggle_mute"] = "volume_up"
    with pytest.raises(ValueError, match="tylko dla akcji Media"):
        validate_config(config)
    with pytest.raises(ValueError, match="modyfikatorów"):
        validate_action_shortcut("media.volume_up", "ctrl+volume_up")

