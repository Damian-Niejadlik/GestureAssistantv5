from pathlib import Path

from src.gesture_assistant.core.config_manager import project_config_path


def test_default_config_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    requested = project_config_path()
    assert requested.is_absolute()
    assert requested.parent != tmp_path
    assert requested.name == "config.json"
    assert project_config_path("custom.json") == Path("custom.json")


def test_confirmation_requires_two_seconds_and_executes_only_once():
    from src.gesture_assistant.core.action_runtime import ActionRuntime
    from src.gesture_assistant.gestures.definitions import Gesture
    from tests.action_samples import Clock, analysis, context, policy

    clock = Clock()
    action = "system.close_active_window"
    config = policy(action)
    config["bindings"] = {"FIST": action}
    config["safety"]["confirmed_destructive"] = [action]
    detector = context(clock, "notepad.exe")
    runtime = ActionRuntime(config, detector, clock)
    calls = []
    runtime.executor.handlers[action] = lambda: calls.append(action)
    runtime.executor.dry_run = False
    for stamp in range(0, 701, 100):
        clock.value = stamp
        runtime.observe(analysis(stamp))
    assert runtime.process_one().reason == "explicit_confirmation_required"
    for stamp in range(800, 2701, 100):
        clock.value = stamp
        runtime.observe(analysis(stamp, Gesture.DOUBLE_THUMBS_UP))
        assert runtime.process_one() is None
    clock.value = 2800
    runtime.observe(analysis(2800, Gesture.DOUBLE_THUMBS_UP))
    assert runtime.process_one().executed and calls == [action]
    clock.value = 2900
    runtime.observe(analysis(2900, Gesture.DOUBLE_THUMBS_UP))
    assert runtime.process_one() is None and calls == [action]

