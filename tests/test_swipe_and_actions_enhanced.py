from copy import deepcopy

import pytest

from src.gesture_assistant.core.action_runtime import ActionRuntime
from src.gesture_assistant.core.analysis_pipeline import AnalysisPipeline
from src.gesture_assistant.core.config_manager import ConfigManager, defaults
from src.gesture_assistant.gestures.classifier import GestureClassifier
from src.gesture_assistant.gestures.definitions import Gesture, Motion, Quality
from src.gesture_assistant.gestures.motion_classifier import MotionClassifier
from tests.action_samples import Clock, analysis, context, policy
from tests.gesture_samples import frame, sample





@pytest.mark.parametrize(
    "start, end, expected",
    [
        ((0.2, 0.5), (0.55, 0.5), Motion.SWIPE_RIGHT),
        ((0.7, 0.5), (0.35, 0.5), Motion.SWIPE_LEFT),
        ((0.5, 0.7), (0.5, 0.35), Motion.SWIPE_UP),
        ((0.5, 0.3), (0.5, 0.65), Motion.SWIPE_DOWN),
    ],
)
def test_swipes_all_four_directions(start, end, expected):
    classifier = MotionClassifier()
    steps = 4
    res = Motion.NONE
    for i in range(steps):
        x = start[0] + (end[0] - start[0]) * (i / (steps - 1))
        y = start[1] + (end[1] - start[1]) * (i / (steps - 1))
        res = classifier.update((x, y), Gesture.OPEN_PALM, i * 60)
    assert res == expected





def test_swipe_fast_motion():
    """Szybki ruch (3 klatki, 60 ms, duży krok)."""
    classifier = MotionClassifier()
    assert classifier.update((0.2, 0.5), Gesture.OPEN_PALM, 0) == Motion.NONE
    assert classifier.update((0.35, 0.5), Gesture.OPEN_PALM, 30) == Motion.NONE
    res = classifier.update((0.52, 0.5), Gesture.OPEN_PALM, 60)
    assert res == Motion.SWIPE_RIGHT


def test_swipe_slow_motion():
    """Wolniejszy ruch (10 klatek w ciągu 500 ms, poniżej limitu 700 ms)."""
    classifier = MotionClassifier()
    res = Motion.NONE
    for i in range(10):
        x = 0.2 + (0.32 * (i / 9))
        res = classifier.update((x, 0.5), Gesture.OPEN_PALM, i * 50)
    assert res == Motion.SWIPE_RIGHT


def test_swipe_exceeding_max_duration_is_rejected():
    """Ruch zbyt powolny (przekraczający 700 ms)."""
    classifier = MotionClassifier()
    res = Motion.NONE
    for i in range(10):
        x = 0.2 + (0.32 * (i / 9))
        res = classifier.update((x, 0.5), Gesture.OPEN_PALM, i * 100)
    assert res == Motion.NONE





@pytest.mark.parametrize("fps, interval_ms", [(15, 66), (30, 33), (60, 16)])
def test_swipe_variable_fps(fps, interval_ms):
    classifier = MotionClassifier()
    total_time_ms = 300
    n_frames = max(4, total_time_ms // interval_ms)
    res = Motion.NONE
    for i in range(n_frames):
        x = 0.2 + 0.3 * (i / (n_frames - 1))
        t = i * interval_ms
        res = classifier.update((x, 0.5), Gesture.OPEN_PALM, t)
    assert res == Motion.SWIPE_RIGHT





def test_swipe_tolerates_brief_unknown_during_trajectory():
    """Chwilowe zaburzenie (UNKNOWN) nie kasuje trajektorii, jeśli dłoń pozostaje stabilna."""
    classifier = MotionClassifier()
    assert classifier.update((0.20, 0.5), Gesture.OPEN_PALM, 0) == Motion.NONE
    assert classifier.update((0.28, 0.5), Gesture.UNKNOWN, 50) == Motion.NONE
    assert classifier.update((0.38, 0.5), Gesture.UNKNOWN, 100) == Motion.NONE
    res = classifier.update((0.52, 0.5), Gesture.OPEN_PALM, 150)
    assert res == Motion.SWIPE_RIGHT


def test_swipe_without_any_open_palm_is_rejected():
    """Ruch wykonany wyłącznie z gestem UNKNOWN nie jest klasyfikowany jako swipe."""
    classifier = MotionClassifier()
    for i in range(5):
        x = 0.2 + 0.3 * (i / 4)
        assert classifier.update((x, 0.5), Gesture.UNKNOWN, i * 50) == Motion.NONE





def test_jitter_without_swipe():
    """Drobne drgania w miejscu nie wywołują swipe."""
    classifier = MotionClassifier()
    jitters = [(0.50, 0.50), (0.52, 0.51), (0.49, 0.49), (0.51, 0.50), (0.50, 0.51)]
    for i, pt in enumerate(jitters):
        assert classifier.update(pt, Gesture.OPEN_PALM, i * 50) == Motion.NONE





def test_hand_loss_resets_motion():
    classifier = MotionClassifier()
    assert classifier.update((0.2, 0.5), Gesture.OPEN_PALM, 0) == Motion.NONE
    assert classifier.update((0.3, 0.5), Gesture.OPEN_PALM, 50) == Motion.NONE

    assert classifier.update(None, Gesture.NONE, 100) == Motion.NONE

    assert classifier.update((0.4, 0.5), Gesture.OPEN_PALM, 150) == Motion.NONE
    assert classifier.update((0.5, 0.5), Gesture.OPEN_PALM, 200) == Motion.NONE


def test_position_jump_teleport_resets_motion():
    classifier = MotionClassifier()
    assert classifier.update((0.1, 0.5), Gesture.OPEN_PALM, 0) == Motion.NONE

    assert classifier.update((0.65, 0.5), Gesture.OPEN_PALM, 50) == Motion.NONE
    assert classifier.update((0.75, 0.5), Gesture.OPEN_PALM, 100) == Motion.NONE


def test_conflicting_static_gesture_resets_motion():
    classifier = MotionClassifier()
    assert classifier.update((0.2, 0.5), Gesture.OPEN_PALM, 0) == Motion.NONE

    assert classifier.update((0.35, 0.5), Gesture.FIST, 50) == Motion.NONE
    assert classifier.update((0.55, 0.5), Gesture.OPEN_PALM, 100) == Motion.NONE





def test_single_swipe_produces_single_event_and_subsequent_swipe_after_cooldown():
    classifier = MotionClassifier()

    assert classifier.update((0.2, 0.5), Gesture.OPEN_PALM, 0) == Motion.NONE
    assert classifier.update((0.3, 0.5), Gesture.OPEN_PALM, 50) == Motion.NONE
    assert classifier.update((0.4, 0.5), Gesture.OPEN_PALM, 100) == Motion.NONE
    res1 = classifier.update((0.52, 0.5), Gesture.OPEN_PALM, 150)
    assert res1 == Motion.SWIPE_RIGHT


    assert classifier.update((0.55, 0.5), Gesture.OPEN_PALM, 200) == Motion.NONE
    assert classifier.update((0.60, 0.5), Gesture.OPEN_PALM, 300) == Motion.NONE


    for i in range(4):
        assert (
            classifier.update((0.2 + i * 0.1, 0.5), Gesture.OPEN_PALM, 500 + i * 50) == Motion.NONE
        )


    t_base = 1800
    assert classifier.update((0.2, 0.5), Gesture.OPEN_PALM, t_base) == Motion.NONE
    assert classifier.update((0.3, 0.5), Gesture.OPEN_PALM, t_base + 50) == Motion.NONE
    assert classifier.update((0.4, 0.5), Gesture.OPEN_PALM, t_base + 100) == Motion.NONE
    res2 = classifier.update((0.52, 0.5), Gesture.OPEN_PALM, t_base + 150)
    assert res2 == Motion.SWIPE_RIGHT





def test_full_pipeline_to_handler_swipe():
    """Zdarzenie swipe z AnalysisPipeline przechodzi autoryzację i trafia do handlera."""
    clock = Clock()
    cfg = policy("presentation.next_slide")
    cfg["profiles"]["Presentation"]["SWIPE_RIGHT"] = "presentation.next_slide"
    cfg["allowed_actions"] = ["presentation.next_slide"]
    cfg["execution"]["dry_run"] = False

    det = context(clock, "powerpnt.exe")
    runtime = ActionRuntime(cfg, det, clock)
    calls = []
    runtime.executor.handlers = {"presentation.next_slide": lambda: calls.append("next")}
    runtime.executor.dry_run = False
    runtime.resume()


    pipeline = AnalysisPipeline()
    for i in range(4):
        t = i * 100
        clock.value = t
        h = sample(Gesture.OPEN_PALM, scale=0.5, dx=-0.2 + i * 0.1)
        res = pipeline.process(frame(h, t), 100, 100)
        runtime.observe(res)


    assert len(runtime.queue) == 1
    outcome = runtime.process_one()
    assert outcome is not None
    assert outcome.executed
    assert outcome.action_id == "presentation.next_slide"
    assert calls == ["next"]





def test_paused_blocks_execution():
    clock = Clock()
    cfg = policy("teams.toggle_mute")
    cfg["safety"]["paused"] = True
    runtime = ActionRuntime(cfg, context(clock), clock)
    assert runtime.safety.paused


    for t in range(0, 701, 100):
        clock.value = t
        runtime.observe(analysis(t, Gesture.FIST))
    assert len(runtime.queue) == 0
    assert runtime.process_one() is None


def test_dry_run_accepts_without_executing_handler():
    clock = Clock()
    cfg = policy("teams.toggle_mute")
    cfg["execution"]["dry_run"] = True
    runtime = ActionRuntime(cfg, context(clock), clock)
    runtime.resume()
    calls = []
    runtime.executor.handlers = {"teams.toggle_mute": lambda: calls.append(1)}

    for t in range(0, 701, 100):
        clock.value = t
        runtime.observe(analysis(t, Gesture.FIST))

    assert len(runtime.queue) == 1
    outcome = runtime.process_one()
    assert outcome is not None
    assert outcome.accepted
    assert not outcome.executed
    assert outcome.reason == "dry_run_no_side_effect"
    assert not calls


def test_live_executes_handler():
    clock = Clock()
    cfg = policy("teams.toggle_mute")
    cfg["execution"]["dry_run"] = False
    runtime = ActionRuntime(cfg, context(clock), clock)
    runtime.executor.dry_run = False
    runtime.resume()
    calls = []
    runtime.executor.handlers = {"teams.toggle_mute": lambda: calls.append(1)}

    for t in range(0, 701, 100):
        clock.value = t
        runtime.observe(analysis(t, Gesture.FIST))

    assert len(runtime.queue) == 1
    outcome = runtime.process_one()
    assert outcome is not None
    assert outcome.executed
    assert calls == [1]


def test_not_allowed_action_blocks_request():
    clock = Clock()
    cfg = policy("teams.toggle_mute")
    cfg["allowed_actions"] = []
    runtime = ActionRuntime(cfg, context(clock), clock)
    runtime.resume()

    for t in range(0, 701, 100):
        clock.value = t
        runtime.observe(analysis(t, Gesture.FIST))

    assert len(runtime.queue) == 0





def test_global_bindings_override_profile_and_none_action_does_not_inherit():
    clock = Clock()
    cfg = defaults()
    cfg["safety"]["enabled"] = True
    cfg["safety"]["paused"] = False


    assert cfg["profiles"]["Media"]["FIST"] == "media.play_pause"


    cfg["bindings"]["FIST"] = "system.toggle_mute"
    cfg["allowed_actions"] = ["system.toggle_mute", "media.play_pause"]

    runtime = ActionRuntime(cfg, context(clock, "vlc.exe"), clock)
    runtime.resume()


    for t in range(0, 701, 100):
        clock.value = t
        runtime.observe(analysis(t, Gesture.FIST))


    diag = runtime.diagnostics()
    assert diag["effective_action"] == "system.toggle_mute"
    assert diag["action_source"] == "Globalne"


    cfg["bindings"]["FIST"] = "none"
    runtime.apply_config(cfg)
    runtime.resume()

    for t in range(800, 1501, 100):
        clock.value = t
        runtime.observe(analysis(t, Gesture.FIST))

    diag2 = runtime.diagnostics()
    assert diag2["effective_action"] is None
    assert diag2["action_source"] == "Brak akcji (Globalne)"
    assert len(runtime.queue) == 0





def test_config_save_load_and_dynamic_apply(tmp_path):
    cfg_file = tmp_path / "test_config.json"
    manager = ConfigManager(cfg_file)
    cfg = defaults()
    cfg["thresholds"]["swipe_distance"] = 0.20
    cfg["thresholds"]["gesture_hold_ms"] = 800
    cfg["bindings"]["SWIPE_UP"] = "system.lock"
    manager.save(cfg)

    loaded = manager.load().config
    assert loaded["thresholds"]["swipe_distance"] == 0.20
    assert loaded["thresholds"]["gesture_hold_ms"] == 800
    assert loaded["bindings"]["SWIPE_UP"] == "system.lock"


    clock = Clock()
    runtime = ActionRuntime(defaults(), context(clock), clock)
    runtime.apply_config(loaded)
    assert runtime.safety.config["thresholds"]["gesture_hold_ms"] == 800
    assert runtime.safety.paused


def test_apply_config_invalidates_pending_requests():
    clock = Clock()
    cfg = policy("teams.toggle_mute")
    runtime = ActionRuntime(cfg, context(clock), clock)
    runtime.resume()


    for t in range(0, 701, 100):
        clock.value = t
        runtime.observe(analysis(t, Gesture.FIST))
    assert len(runtime.queue) == 1


    new_cfg = deepcopy(cfg)
    new_cfg["thresholds"]["gesture_hold_ms"] = 900
    runtime.apply_config(new_cfg)


    assert len(runtime.queue) == 0
    assert runtime.process_one() is None





@pytest.mark.parametrize(
    "gesture",
    [
        Gesture.OPEN_PALM,
        Gesture.FIST,
        Gesture.THUMBS_UP,
        Gesture.THUMBS_DOWN,
        Gesture.VICTORY,
        Gesture.POINTING_UP,
        Gesture.PINCH,
        Gesture.ROCK,
    ],
)
def test_static_gestures_classification_and_confidence(gesture):
    classifier = GestureClassifier()
    hand_sample = sample(gesture)
    res = classifier.classify(hand_sample)
    assert res.gesture == gesture
    assert res.quality == Quality.VALID
    assert 0.70 <= res.confidence <= 0.85

