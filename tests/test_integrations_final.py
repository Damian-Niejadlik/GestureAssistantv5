import pytest

from src.gesture_assistant.config.schema import validate_config
from src.gesture_assistant.core.action_executor import ActionExecutor
from src.gesture_assistant.core.config_manager import defaults
from src.gesture_assistant.gestures.definitions import Gesture
from src.gesture_assistant.integrations import browser_actions
from src.gesture_assistant.integrations.dispatcher import NativeDispatcher
from src.gesture_assistant.integrations.keyboard_actions import validate_shortcut
from tests.action_samples import feed, policy, ready
from tests.integration_samples import FakeKeyboard

ACTIONS = [
    ("presentation.next_slide", "powerpnt.exe", "right"),
    ("presentation.previous_slide", "powerpnt.exe", "left"),
    ("presentation.start_presentation", "powerpnt.exe", "f5"),
    ("presentation.end_presentation", "powerpnt.exe", "escape"),
    ("media.play_pause", "vlc.exe", "media_play_pause"),
    ("media.stop", "vlc.exe", "media_stop"),
    ("media.volume_up", "spotify.exe", "volume_up"),
    ("media.volume_down", "wmplayer.exe", "volume_down"),
    ("media.next_track", "vlc.exe", "media_next_track"),
    ("media.previous_track", "vlc.exe", "media_previous_track"),
]


@pytest.mark.parametrize("action_id, executable, expected", ACTIONS)
def test_authorized_executor_to_dispatcher_with_fake_keyboard(action_id, executable, expected):
    safety, clock, detector = ready(action_id, executable)
    keyboard = FakeKeyboard()
    dispatcher = NativeDispatcher(safety.config, keyboard)
    request = safety.request(action_id, "FIST", detector.detect())
    assert request is not None
    executor = ActionExecutor(safety, detector, dry_run=False, dispatcher=dispatcher)
    outcome = executor.execute(request)
    assert outcome.executed and keyboard.calls[0][0] == expected
    assert not executor.execute(request).executed


@pytest.mark.parametrize("action_id, executable, expected", ACTIONS)
def test_paused_and_teams_context_block_native_path(action_id, executable, expected):
    safety, clock, detector = ready(action_id, executable)
    request = safety.request(action_id, "FIST", detector.detect())
    keyboard = FakeKeyboard()
    executor = ActionExecutor(
        safety,
        detector,
        dry_run=False,
        dispatcher=NativeDispatcher(safety.config, keyboard),
    )
    safety.pause()
    assert not executor.execute(request).executed
    assert not keyboard.calls
    safety, clock, detector = ready(action_id, "ms-teams.exe")
    assert safety.request(action_id, "FIST", detector.detect()) is None


@pytest.mark.parametrize("action_id, executable, expected", ACTIONS)
def test_action_cooldown_applies_across_different_gestures(action_id, executable, expected):
    safety, clock, detector = ready(action_id, executable)
    request = safety.request(action_id, "FIST", detector.detect())
    assert safety.reserve(request, detector.detect()) == ""
    safety.finish(request)
    feed(safety, clock, 800, 1500, Gesture.OPEN_PALM)
    assert safety.request(action_id, "OPEN_PALM", detector.detect()) is None
    feed(safety, clock, 1600, 2700, Gesture.OPEN_PALM)
    assert safety.request(action_id, "OPEN_PALM", detector.detect()) is not None


def test_forced_mode_does_not_send_media_keys_to_powerpoint():
    config = policy("media.play_pause")
    config["mode"] = "Media"
    safety, clock, detector = ready("media.play_pause", "powerpnt.exe", config)
    assert detector.detect("Media").profile.value == "Media"
    assert safety.request("media.play_pause", "FIST", detector.detect("Media")) is None


@pytest.mark.parametrize(
    "value",
    [
        "",
        "javascript:alert(1)",
        "file:///tmp/file",
        "https://x:bad/",
        "https://user:secret@example.com",
        "https://a b",
    ],
)
def test_invalid_url_never_opens_browser(monkeypatch, value):
    calls = []
    monkeypatch.setattr(browser_actions.webbrowser, "open", lambda *a, **k: calls.append(a))
    with pytest.raises(ValueError):
        browser_actions.open_url(value, lambda: True)
    assert not calls


def test_valid_url_uses_guard_and_reports_handler_failure(monkeypatch):
    monkeypatch.setattr(browser_actions.webbrowser, "open", lambda *a, **k: False)
    with pytest.raises(OSError):
        browser_actions.open_url("https://example.com", lambda: True)


@pytest.mark.parametrize("shortcut", ["ctrl++m", "ctrl+ctrl+m", "ctrl+alt+delete", "unknown", ""])
def test_invalid_shortcut(shortcut):
    with pytest.raises(ValueError):
        validate_shortcut(shortcut)


def test_configuration_contains_new_profiles_but_remains_disabled():
    config = defaults()
    assert config["profiles"]["Presentation"]["SWIPE_RIGHT"] == "presentation.next_slide"
    assert config["profiles"]["Media"]["FIST"] == "media.play_pause"
    assert config["safety"]["paused"] and not config["safety"]["enabled"]
    assert config["execution"]["dry_run"] and not config["safety"]["sleep_computer"]
    assert validate_config(config) == config


@pytest.mark.parametrize("action_id, executable, expected", ACTIONS)
def test_dry_run_never_calls_native_backend(action_id, executable, expected):
    safety, clock, detector = ready(action_id, executable)
    keyboard = FakeKeyboard()
    request = safety.request(action_id, "FIST", detector.detect())
    executor = ActionExecutor(
        safety,
        detector,
        dry_run=True,
        dispatcher=NativeDispatcher(safety.config, keyboard),
    )
    result = executor.execute(request)
    assert result.accepted and not result.executed
    assert result.reason == "dry_run_no_side_effect"
    assert not keyboard.calls

