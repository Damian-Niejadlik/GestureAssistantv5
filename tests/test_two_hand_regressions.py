from dataclasses import replace

import pytest

from src.gesture_assistant.core.analysis_pipeline import AnalysisPipeline
from src.gesture_assistant.gestures.definitions import Gesture, Quality
from src.gesture_assistant.vision.hand_provider import HandResult
from tests.gesture_samples import sample


@pytest.mark.parametrize("pose, expected", [
    (Gesture.FIST, Gesture.DOUBLE_FIST),
    (Gesture.THUMBS_UP, Gesture.DOUBLE_THUMBS_UP),
])
@pytest.mark.parametrize("swap", [False, True])
@pytest.mark.parametrize("scale", [0.65, 0.8])
def test_pair_recognition(pose, expected, swap, scale):
    hands = (sample(pose, "Left", dx=-0.16, scale=scale),
             sample(pose, "Right", dx=0.16, scale=scale))
    result = AnalysisPipeline().process(HandResult(1, 0, hands[::-1] if swap else hands), 100, 100)
    assert result.gesture == expected and result.quality == Quality.VALID


@pytest.mark.parametrize("swap", [False, True])
@pytest.mark.parametrize("scale", [0.65, 0.8])
def test_triangle_recognition(swap, scale):
    def hand(side, dx):
        model = sample(Gesture.OPEN_PALM, side, dx=dx, scale=scale)
        points = list(model.landmarks)
        points[8] = replace(points[8], x=0.5, y=0.39)
        points[4] = replace(points[4], x=0.5, y=0.63)
        return replace(model, landmarks=tuple(points))

    hands = (hand("Left", -0.16), hand("Right", 0.16))
    result = AnalysisPipeline().process(HandResult(1, 0, hands[::-1] if swap else hands), 100, 100)
    assert result.gesture == Gesture.TRIANGLE and result.quality == Quality.VALID

