import pytest

from src.gesture_assistant.gestures.definitions import Gesture, Motion
from src.gesture_assistant.gestures.motion_classifier import MotionClassifier


@pytest.mark.parametrize(
    "delta, expected",
    [
        ((0.1, 0), Motion.SWIPE_RIGHT),
        ((-0.1, 0), Motion.SWIPE_LEFT),
        ((0, 0.1), Motion.SWIPE_DOWN),
        ((0, -0.1), Motion.SWIPE_UP),
    ],
)
def test_four_swipes(delta, expected):
    classifier = MotionClassifier()
    result = Motion.NONE
    for i in range(4):
        result = classifier.update(
            (0.5 + i * delta[0], 0.5 + i * delta[1]), Gesture.OPEN_PALM, i * 100
        )
    assert result == expected
    assert classifier.update((0.8, 0.5), Gesture.OPEN_PALM, 400) == Motion.NONE


@pytest.mark.parametrize("gesture", [Gesture.FIST, Gesture.UNKNOWN, Gesture.NONE])
def test_only_open_palm(gesture):
    classifier = MotionClassifier()
    for i in range(4):
        assert classifier.update((0.2 + i * 0.1, 0.5), gesture, i * 100) == Motion.NONE


def test_too_slow_diagonal_jitter_and_teleport():
    for points, times in [
        ([(0.2 + i * 0.1, 0.5) for i in range(4)], [0, 300, 600, 900]),
        ([(0.2 + i * 0.1, 0.2 + i * 0.1) for i in range(4)], [0, 100, 200, 300]),
        ([(0.5, 0.5), (0.51, 0.5), (0.49, 0.5), (0.51, 0.5)], [0, 100, 200, 300]),
        ([(0.1, 0.5), (0.7, 0.5), (0.71, 0.5)], [0, 100, 200]),
    ]:
        classifier = MotionClassifier()
        for point, timestamp in zip(points, times, strict=True):
            assert classifier.update(point, Gesture.OPEN_PALM, timestamp) == Motion.NONE


def test_gesture_change_resets_trajectory():
    c = MotionClassifier()
    assert c.update((0.2, 0.5), Gesture.OPEN_PALM, 0) == Motion.NONE
    assert c.update((0.3, 0.5), Gesture.FIST, 100) == Motion.NONE
    assert c.update((0.5, 0.5), Gesture.OPEN_PALM, 200) == Motion.NONE


def test_threshold_not_crossed():
    c = MotionClassifier()
    for i, x in enumerate((0.2, 0.3, 0.449, 0.448)):
        assert c.update((x, 0.5), Gesture.OPEN_PALM, i * 100) == Motion.NONE


def test_cooldown_expiry_and_missing_points():
    c = MotionClassifier()
    for i in range(4):
        result = c.update((0.2 + i * 0.1, 0.5), Gesture.OPEN_PALM, i * 100)
    assert result == Motion.SWIPE_RIGHT
    assert c.update(None, Gesture.NONE, 400) == Motion.NONE
    for i in range(4):
        result = c.update((0.2 + i * 0.1, 0.5), Gesture.OPEN_PALM, 1800 + i * 100)
    assert result == Motion.SWIPE_RIGHT


def test_backtracking_not_smooth():
    c = MotionClassifier()

    for i, x in enumerate((0.1, 0.25, 0.15, 0.3, 0.4)):
        assert c.update((x, 0.5), Gesture.OPEN_PALM, i * 100) == Motion.NONE


def test_trajectory_longer_than_window_never_reaches_distance():
    c = MotionClassifier()
    for i in range(5):
        assert c.update((0.2 + i * 0.0625, 0.5), Gesture.OPEN_PALM, i * 200) == Motion.NONE

