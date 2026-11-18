from dataclasses import replace

from src.gesture_assistant.core.action_executor import ActionExecutor
from src.gesture_assistant.core.action_queue import ActionQueue
from src.gesture_assistant.gestures.definitions import Gesture, Motion, Quality
from tests.action_samples import analysis, context, feed, policy, ready


def test_requires_real_700ms_not_five_fast_frames():
    safety, clock, detector = ready()
    safety.resume()
    feed(safety, clock, 800, 1200)
    assert safety.request("teams.toggle_mute", "FIST", detector.detect()) is None
    feed(safety, clock, 1300, 1500)
    assert safety.request("teams.toggle_mute", "FIST", detector.detect()) is not None


def test_pause_invalidates_pending_and_configuration_is_not_mutable():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    assert request is not None
    config = safety.config
    config["safety"]["paused"] = True
    assert not safety.paused
    safety.pause()
    assert safety.reserve(request, detector.detect()) == "invalid_or_consumed_request"
    assert safety.request("teams.toggle_mute", "FIST", detector.detect()) is None


def test_cooldown_release_replay_and_dryrun():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    executor = ActionExecutor(safety, detector)
    outcome = executor.execute(request)
    assert outcome.accepted and not outcome.executed
    assert executor.execute(request).reason == "invalid_or_consumed_request"
    feed(safety, clock, 800, 2800)
    assert safety.request("teams.toggle_mute", "FIST", detector.detect()) is None
    feed(safety, clock, 2900, 3900, Gesture.NONE, Quality.NO_HAND)
    feed(safety, clock, 4000, 4700)
    assert safety.request("teams.toggle_mute", "FIST", detector.detect()) is not None


def test_system_actions_blocked_in_teams_and_browser():
    for name in ("ms-teams.exe", "chrome.exe"):
        safety, clock, detector = ready("system.lock", name)

        request = safety.request(
            "system.lock",
            "FIST",
            detector.detect(),
        )

        assert request is None

    safety, clock, detector = ready("system.lock", "unknown.exe")

    request = safety.request(
        "system.lock",
        "FIST",
        detector.detect(),
    )

    assert request is not None
    assert request.action_id == "system.lock"

    safety, clock, detector = ready("system.lock", "explorer.exe")
    detector.reader = lambda: None

    request = safety.request(
        "system.lock",
        "FIST",
        detector.detect(),
    )

    assert request is None


def test_sleep_off_and_destructive_confirmation():
    config = policy("sleep_computer")

    safety, clock, detector = ready(
        "sleep_computer",
        "explorer.exe",
        config,
    )

    assert (
        safety.request(
            "sleep_computer",
            "FIST",
            detector.detect(),
        )
        is None
    )

    config["safety"]["sleep_computer"] = True

    safety, clock, detector = ready(
        "sleep_computer",
        "explorer.exe",
        config,
    )

    request = safety.request(
        "sleep_computer",
        "FIST",
        detector.detect(),
    )

    assert request is not None

    assert (
        safety.reserve(
            request,
            detector.detect(),
        )
        == "destructive_not_enabled_in_settings"
    )

    config["safety"]["confirmed_destructive"] = ["sleep_computer"]

    safety, clock, detector = ready(
        "sleep_computer",
        "explorer.exe",
        config,
    )

    request = safety.request(
        "sleep_computer",
        "FIST",
        detector.detect(),
    )

    assert request is not None

    assert (
        safety.reserve(
            request,
            detector.detect(),
        )
        == "explicit_confirmation_required"
    )

    safety.confirm_once(
        "sleep_computer",
        detector.detect(),
    )

    assert (
        safety.request(
            "sleep_computer",
            "FIST",
            detector.detect(),
        )
        is None
    )

    feed(safety, clock, 800, 1500)

    request = safety.request(
        "sleep_computer",
        "FIST",
        detector.detect(),
    )

    assert request is not None
    assert safety.reserve(request, detector.detect()) == ""

    safety.finish(request)


def test_context_revalidated_and_tracking_gap_resets_hold():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    detector.reader = lambda: context(clock, "chrome.exe").reader()
    assert not ActionExecutor(safety, detector).execute(request).accepted
    safety, clock, detector = ready()
    clock.value = 1100
    safety.observe(analysis(1100))
    assert safety.request("teams.toggle_mute", "FIST", detector.detect()) is None


def test_low_quality_and_expired_request():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    clock.value = 1000
    assert not ActionExecutor(safety, detector).execute(request).accepted
    safety.observe(analysis(1000, quality=Quality.LOW_CONFIDENCE))
    assert safety.request("teams.toggle_mute", "FIST", detector.detect()) is None


def test_motion_requires_open_palm_hold_and_cooldown():
    safety, clock, detector = ready()
    feed(safety, clock, 800, 1500, Gesture.OPEN_PALM)
    clock.value = 1600
    safety.observe(analysis(1600, Gesture.OPEN_PALM, motion=Motion.SWIPE_RIGHT))
    request = safety.request("teams.toggle_mute", "SWIPE_RIGHT", detector.detect())
    assert request is not None
    assert safety.reserve(request, detector.detect()) == ""
    safety.finish(request)
    clock.value = 1700
    safety.observe(analysis(1700, Gesture.OPEN_PALM))
    assert safety.request("teams.toggle_mute", "OPEN_PALM", detector.detect()) is None


def test_queue_bounded_and_deduplicated():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    queue = ActionQueue(1)
    assert queue.put(request)
    assert not queue.put(request)
    assert not queue.put(replace(request, token="different"))
    assert queue.pop() == request
    assert queue.pop() is None


def test_timestamp_replay_future_and_long_gap_cannot_fake_release():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    assert safety.reserve(request, detector.detect()) == ""
    safety.finish(request)
    assert not safety.observe(analysis(700))
    clock.value = 800
    assert not safety.observe(analysis(900))
    safety.observe(analysis(800, Gesture.NONE, Quality.NO_HAND))
    clock.value = 5000
    safety.observe(analysis(5000, Gesture.NONE, Quality.NO_HAND))
    feed(safety, clock, 5100, 5800)
    assert safety.request("teams.toggle_mute", "FIST", detector.detect()) is None


def test_default_paused_and_global_two_second_action_cooldown():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    assert safety.reserve(request, detector.detect()) == ""
    safety.finish(request)
    feed(safety, clock, 800, 1500, Gesture.OPEN_PALM)
    assert safety.request("teams.toggle_mute", "OPEN_PALM", detector.detect()) is None
    feed(safety, clock, 1600, 2700, Gesture.OPEN_PALM)
    assert safety.request("teams.toggle_mute", "OPEN_PALM", detector.detect()) is not None


def test_tracking_epoch_change_cannot_bridge_stability():
    safety, clock, detector = ready()
    clock.value = 800
    safety.observe(replace(analysis(800), tracking_epoch=1))
    assert safety.request("teams.toggle_mute", "FIST", detector.detect()) is None

