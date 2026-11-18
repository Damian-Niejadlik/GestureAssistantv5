import threading

from src.gesture_assistant.core.action_executor import ActionExecutor
from src.gesture_assistant.core.action_runtime import ActionRuntime
from tests.action_samples import Clock, analysis, context, policy, ready


def test_only_injected_fake_handler_executes():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    calls = []
    handlers = {"teams.toggle_mute": lambda: calls.append(1)}
    executor = ActionExecutor(safety, detector, handlers, False)
    outcome = executor.execute(request)
    assert outcome.executed and calls == [1]
    assert not executor.execute(request).executed


def test_two_executions_never_overlap():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    entered, release = threading.Event(), threading.Event()
    outcomes = []

    def handler():
        entered.set()
        assert release.wait(3), "Test nie zwolnił handlera."

    executor = ActionExecutor(safety, detector, {"teams.toggle_mute": handler}, False)
    thread = threading.Thread(target=lambda: outcomes.append(executor.execute(request)))
    try:
        thread.start()
        assert entered.wait(3)

        assert executor.execute(request).reason == "busy"
    finally:
        release.set()
        thread.join(timeout=3)
    assert not thread.is_alive()
    assert len(outcomes) == 1 and outcomes[0].executed


def test_failed_handler_has_cooldown_and_does_not_leave_busy_flag():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())

    def fail():
        raise OSError("fake failure")

    outcome = ActionExecutor(safety, detector, {"teams.toggle_mute": fail}, False).execute(request)
    assert not outcome.executed and "handler_error" in outcome.reason
    assert safety._active is None
    assert safety._action_until == clock() + 2000


def test_context_changed_between_two_checks_blocks_fake_handler():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    calls = []
    original_detect = detector.detect

    def changed(mode):
        result = original_detect(mode)
        detector.reader = context(clock, "chrome.exe").reader
        return result

    detector.detect = changed
    handlers = {"teams.toggle_mute": lambda: calls.append(1)}
    outcome = ActionExecutor(safety, detector, handlers, False)
    assert outcome.execute(request).reason == "authorization_changed"
    assert not calls


def test_runtime_uses_continuous_observation_not_early_event():
    clock = Clock()
    config = policy()
    config["bindings"] = {"FIST": "teams.toggle_mute"}
    runtime = ActionRuntime(config, context(clock), clock)
    for stamp in range(0, 701, 100):
        clock.value = stamp
        runtime.observe(analysis(stamp))
        assert len(runtime.queue) == (1 if stamp == 700 else 0)
    runtime.pause()
    assert len(runtime.queue) == 0
    assert runtime.process_one() is None


def test_default_runtime_cannot_issue_actions():
    runtime = ActionRuntime()
    assert runtime.safety.paused
    assert not runtime.safety.config["safety"]["enabled"]
    assert not runtime.executor.handlers
    assert runtime.executor.dry_run


def test_tracking_can_expire_during_context_read():
    safety, clock, detector = ready()
    request = safety.request("teams.toggle_mute", "FIST", detector.detect())
    original_detect = detector.detect
    calls = []

    def slow_detect(mode):
        snapshot = original_detect(mode)
        clock.value += 200
        return snapshot

    detector.detect = slow_detect
    outcome = ActionExecutor(safety, detector, {"teams.toggle_mute": lambda: calls.append(1)})
    assert outcome.execute(request).reason == "authorization_changed"
    assert not calls

