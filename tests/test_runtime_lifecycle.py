import threading

import pytest

from src.gesture_assistant.core.action_executor import ActionExecutor
from src.gesture_assistant.core.action_runtime import ActionRuntime
from tests.action_samples import policy, ready


def test_consumer_starts_stops_and_can_restart_without_os_actions():
    runtime = ActionRuntime()
    for _ in range(2):
        try:
            runtime.start()
            assert runtime.is_running
            with pytest.raises(RuntimeError):
                runtime.start()
        finally:
            runtime.stop()
            runtime._thread.join(timeout=2)
        assert not runtime.is_running
        assert runtime.safety.paused and len(runtime.queue) == 0


def test_a_different_media_action_cannot_start_during_active_handler():
    config = policy("media.play_pause")
    config["allowed_actions"].append("media.stop")
    safety, clock, detector = ready("media.play_pause", "vlc.exe", config)
    request = safety.request("media.play_pause", "FIST", detector.detect())
    entered, release = threading.Event(), threading.Event()
    outcomes = []

    def handler():
        entered.set()
        assert release.wait(2), "Nie zwolniono atrapy handlera."

    executor = ActionExecutor(safety, detector, {"media.play_pause": handler}, False)
    thread = threading.Thread(target=lambda: outcomes.append(executor.execute(request)))
    try:
        thread.start()
        assert entered.wait(2)
        assert safety.request("media.stop", "FIST", detector.detect()) is None
    finally:
        release.set()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert outcomes[0].executed

