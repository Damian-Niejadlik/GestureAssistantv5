import pytest

from src.gesture_assistant.core.debounce import CooldownManager, Debouncer
from src.gesture_assistant.gestures.definitions import Gesture


def test_five_frames_then_latched():
    d = Debouncer()
    for i in range(4):
        assert d.update(Gesture.FIST, i * 20) is None
    assert d.update(Gesture.FIST, 80) == Gesture.FIST
    assert d.update(Gesture.FIST, 5000) is None


def test_time_alternative_and_release():
    d = Debouncer()
    assert d.update(Gesture.FIST, 0) is None
    assert d.update(Gesture.FIST, 700) == Gesture.FIST
    assert d.update(Gesture.NONE, 800) is None
    assert d.update(Gesture.NONE, 1800) is None
    assert d.update(Gesture.FIST, 1801) is None
    assert d.update(Gesture.FIST, 2501) == Gesture.FIST


def test_change_jitter_and_short_release():
    d = Debouncer()
    for i in range(30):
        g = Gesture.FIST if i % 2 else Gesture.PINCH
        assert d.update(g, i * 20) is None
    assert d.update(Gesture.NONE, 900) is None
    for i in range(5):
        event = d.update(Gesture.FIST, 1000 + i)
    assert event == Gesture.FIST
    d.update(Gesture.NONE, 1100)
    assert d.update(Gesture.FIST, 2000) is None
    assert d.update(Gesture.FIST, 5000) is None


def test_cooldown_and_timestamp():
    c = CooldownManager()
    c.start("x", 100, 1500)
    assert c.remaining("x", 1599) == 1
    assert c.remaining("x", 1600) == 0
    d = Debouncer()
    d.update(Gesture.NONE, 1)
    with pytest.raises(ValueError):
        d.update(Gesture.NONE, 1)


def test_tracking_discontinuity_does_not_prove_release():
    d = Debouncer()
    for stamp in range(5):
        event = d.update(Gesture.FIST, stamp)
    assert event == Gesture.FIST
    d.update(Gesture.NONE, 100)
    d.tracking_discontinuity()
    d.update(Gesture.NONE, 5000)
    assert d.update(Gesture.FIST, 5100) is None
    assert d.update(Gesture.FIST, 5800) is None

