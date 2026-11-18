import pytest

from src.gesture_assistant.gestures.smoothing import LandmarkSmoother
from tests.gesture_samples import sample


def test_ema():
    s = LandmarkSmoother(alpha=0.5)
    a = s.update(sample(), 0)
    b = s.update(sample(dx=0.1), 10)
    assert b.landmarks[0].x == pytest.approx(a.landmarks[0].x + 0.05)


def test_loss_and_long_gap_reset():
    s = LandmarkSmoother(alpha=0.5)
    s.update(sample(), 0)
    assert s.update(None, 20) is None
    new = sample(dx=0.1)
    assert s.update(new, 30).landmarks == new.landmarks
    other = sample(dx=-0.1)
    assert s.update(other, 1000).landmarks == other.landmarks


def test_side_switch_resets():
    s = LandmarkSmoother()
    s.update(sample(side="Right"), 0)
    left = sample(side="Left")
    assert s.update(left, 10).landmarks == left.landmarks

