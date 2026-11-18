import os
import threading
from types import SimpleNamespace

import pytest

from src.gesture_assistant.core.action_runtime import ActionRuntime
from src.gesture_assistant.core.analysis_pipeline import AnalysisPipeline
from src.gesture_assistant.core.context_detector import ContextDetector, Foreground
from src.gesture_assistant.gestures.definitions import Gesture, Quality
from src.gesture_assistant.integrations import ACTION_CATALOG, browser_actions
from src.gesture_assistant.integrations.contracts import ContextKind
from tests.action_samples import Clock, analysis, policy
from tests.gesture_samples import frame, sample


def url_runtime(mode="Browser", pid=None, executable="python.exe", dry_run=False):
    clock = Clock()
    config = policy("browser.open_url")
    config["mode"] = mode
    config["execution"]["dry_run"] = dry_run
    config["bindings"] = {"OPEN_PALM": "browser.open_url"}
    config["targets"]["urls"]["browser.open_url"] = "https://example.com/watch"
    foreground = Foreground(71, os.getpid() if pid is None else pid, "C:/Apps/" + executable)
    detector = ContextDetector(lambda: foreground, clock)
    return ActionRuntime(config, detector, clock), clock


def hold(runtime, clock, start=0, end=700, gesture=Gesture.OPEN_PALM):
    for stamp in range(start, end + 1, 100):
        clock.value = stamp
        runtime.observe(analysis(stamp, gesture))


def test_open_palm_from_assistant_calls_webbrowser_once(monkeypatch):
    calls = []
    monkeypatch.setattr(
        browser_actions.webbrowser,
        "open",
        lambda url, **kwargs: calls.append((url, kwargs)) or True,
    )
    runtime, clock = url_runtime()
    hold(runtime, clock)
    outcome = runtime.process_one()
    assert outcome is not None and outcome.executed
    assert calls == [("https://example.com/watch", {"new": 2, "autoraise": False})]
    hold(runtime, clock, 800, 2000)
    assert runtime.process_one() is None
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["Auto", "Teams", "Browser", "Presentation", "Media", "System"])
def test_explicit_url_binding_launches_without_requiring_browser_focus(monkeypatch, mode):
    calls = []
    monkeypatch.setattr(browser_actions.webbrowser, "open", lambda *a, **k: calls.append(a) or True)
    runtime, clock = url_runtime(mode, 42, "explorer.exe")
    hold(runtime, clock)
    outcome = runtime.process_one()
    assert outcome.executed and len(calls) == 1


@pytest.mark.parametrize(
    "action",
    [
        "browser.new_tab",
        "system.lock",
        "teams.toggle_mute",
        "media.play_pause",
        "presentation.next_slide",
    ],
)
def test_own_window_never_accepts_targeted_shortcuts(action):
    runtime, clock = url_runtime()
    config = runtime.safety.config
    config["mode"] = ACTION_CATALOG[action].context.value
    config["allowed_actions"] = [action]
    config["bindings"] = {"OPEN_PALM": action}
    runtime.apply_config(config)
    runtime.resume()
    hold(runtime, clock)
    assert runtime.detector.detect(config["mode"]).kind == ContextKind.UNKNOWN
    assert len(runtime.queue) == 0
    assert runtime.diagnostics()["reason"] == "assistant_window_not_target"


def test_url_unknown_foreground_fails_closed(monkeypatch):
    calls = []
    monkeypatch.setattr(browser_actions.webbrowser, "open", lambda *a, **k: calls.append(a))
    runtime, clock = url_runtime()
    runtime.detector.reader = lambda: None
    hold(runtime, clock)
    assert runtime.process_one() is None
    assert runtime.diagnostics()["reason"] == "unknown_or_stale_context"
    assert not calls


@pytest.mark.parametrize("condition", ["paused", "disabled", "not_allowed", "dry_run"])
def test_url_still_requires_explicit_authorization(monkeypatch, condition):
    calls = []
    monkeypatch.setattr(browser_actions.webbrowser, "open", lambda *a, **k: calls.append(a) or True)
    runtime, clock = url_runtime(dry_run=condition == "dry_run")
    if condition == "paused":
        runtime.pause()
    elif condition in ("disabled", "not_allowed"):
        config = runtime.safety.config
        if condition == "disabled":
            config["safety"]["enabled"] = False
        else:
            config["allowed_actions"] = []
        runtime.apply_config(config)
        runtime.resume()
    hold(runtime, clock)
    outcome = runtime.process_one()
    if condition == "dry_run":
        assert outcome.accepted and not outcome.executed
    else:
        assert outcome is None
    assert not calls


def test_url_waits_full_700ms(monkeypatch):
    calls = []
    monkeypatch.setattr(browser_actions.webbrowser, "open", lambda *a, **k: calls.append(a) or True)
    runtime, clock = url_runtime()
    hold(runtime, clock, end=600)
    assert runtime.process_one() is None
    clock.value = 699
    runtime.observe(analysis(699, Gesture.OPEN_PALM))
    assert runtime.process_one() is None
    clock.value = 700
    runtime.observe(analysis(700, Gesture.OPEN_PALM))
    assert runtime.process_one().executed and len(calls) == 1


def test_real_consumer_thread_reaches_fake_browser(monkeypatch):
    called = threading.Event()
    calls = []

    def fake_open(url, **kwargs):
        calls.append(url)
        called.set()
        return True

    monkeypatch.setattr(browser_actions.webbrowser, "open", fake_open)
    runtime, clock = url_runtime()
    runtime.start()
    try:
        hold(runtime, clock)
        assert called.wait(2), "Konsument nie dotarł do browser.open_url."
    finally:
        runtime.stop()
        runtime._thread.join(timeout=2)
    assert not runtime.is_running
    assert runtime.status().executed and len(calls) == 1


def test_real_pipeline_to_url_from_own_window(monkeypatch):
    calls = []
    monkeypatch.setattr(browser_actions.webbrowser, "open", lambda *a, **k: calls.append(a) or True)
    runtime, clock = url_runtime()
    pipeline = AnalysisPipeline()
    for stamp in range(0, 701, 100):
        clock.value = stamp
        runtime.observe(pipeline.process(frame(sample(Gesture.OPEN_PALM), stamp), 100, 100))
    assert runtime.process_one().executed
    assert len(calls) == 1


@pytest.mark.parametrize(
    "smoothed, raw, expected, confidence",
    [
        (Gesture.UNKNOWN, Gesture.OPEN_PALM, Gesture.OPEN_PALM, 0.85),
        (Gesture.OPEN_PALM, Gesture.UNKNOWN, Gesture.OPEN_PALM, 0.81),
        (Gesture.OPEN_PALM, Gesture.FIST, Gesture.UNKNOWN, 0.0),
    ],
)
def test_confidence_matches_the_selected_classifier(
    monkeypatch,
    smoothed,
    raw,
    expected,
    confidence,
):
    pipeline = AnalysisPipeline()
    results = iter(
        [
            SimpleNamespace(gesture=smoothed, confidence=0.81),
            SimpleNamespace(gesture=raw, confidence=0.85),
        ]
    )
    monkeypatch.setattr(pipeline.gestures.classifier, "classify", lambda *args: next(results))
    result = pipeline.process(frame(sample(), 0), 100, 100)
    assert result.gesture == expected and result.confidence == confidence


def test_diagnostics_refresh_after_tracking_becomes_stale():
    runtime, clock = url_runtime()
    hold(runtime, clock)
    assert runtime.diagnostics()["effective_action"] == "browser.open_url"
    clock.value = 1500
    runtime.observe(analysis(800, Gesture.OPEN_PALM))
    assert runtime.diagnostics()["reason"] == "stale_tracking"
    assert runtime.diagnostics()["tracking_reason"] == "stale_tracking"
    assert len(runtime.queue) == 0


def test_diagnostics_refresh_after_hand_is_lost():
    runtime, clock = url_runtime()
    hold(runtime, clock)
    clock.value = 800
    runtime.observe(analysis(800, Gesture.NONE, Quality.NO_HAND))
    diag = runtime.diagnostics()
    assert diag["gesture"] == "NONE"
    assert diag["tracking_reason"] == "tracking_quality_no_hand"
    assert len(runtime.queue) == 0


def test_switching_live_revokes_already_queued_dry_run():
    runtime, clock = url_runtime(dry_run=True)
    hold(runtime, clock)
    assert len(runtime.queue) == 1
    runtime.set_dry_run(False)
    assert runtime.safety.paused and len(runtime.queue) == 0
    assert not runtime.executor.dry_run
    assert not runtime.safety.config["execution"]["dry_run"]
    assert runtime.process_one() is None
    runtime.resume()
    hold(runtime, clock, 800, 1400)
    assert runtime.process_one() is None
    clock.value = 1500
    runtime.observe(analysis(1500, Gesture.OPEN_PALM))
    assert len(runtime.queue) == 1


def test_only_open_url_is_exempt_from_foreground_target():
    assert {name for name, spec in ACTION_CATALOG.items() if not spec.requires_target} == {
        "browser.open_url",
    }


def test_url_failure_is_reported_and_does_not_stick_busy(monkeypatch):
    monkeypatch.setattr(browser_actions.webbrowser, "open", lambda *a, **k: False)
    runtime, clock = url_runtime()
    hold(runtime, clock)
    result = runtime.process_one()
    assert not result.executed and result.reason.startswith("handler_error:")
    assert runtime.safety._active is None


def test_saved_live_config_still_requires_explicit_resume(monkeypatch):
    config = policy("browser.open_url")
    config["mode"] = "Browser"
    config["execution"]["dry_run"] = False
    config["safety"]["paused"] = True
    config["bindings"] = {"OPEN_PALM": "browser.open_url"}
    config["targets"]["urls"]["browser.open_url"] = "https://example.com"
    clock = Clock()
    own = Foreground(71, os.getpid(), "C:/Apps/python.exe")
    runtime = ActionRuntime(config, ContextDetector(lambda: own, clock), clock)
    calls = []
    monkeypatch.setattr(browser_actions.webbrowser, "open", lambda *a, **k: calls.append(a) or True)
    hold(runtime, clock)
    assert runtime.process_one() is None
    runtime.resume()
    hold(runtime, clock, 800, 1500)
    assert runtime.process_one().executed
    expected = config["targets"]["urls"]["browser.open_url"]
    assert calls == [(expected,)]

