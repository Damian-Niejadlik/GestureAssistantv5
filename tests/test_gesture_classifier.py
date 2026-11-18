from dataclasses import replace

import pytest

from src.gesture_assistant.gestures.classifier import GestureClassifier
from src.gesture_assistant.gestures.definitions import Gesture, Quality
from src.gesture_assistant.gestures.personal import SINGLE
from src.gesture_assistant.vision.hand_provider import HandPoint
from tests.gesture_samples import low_score, sample


@pytest.mark.parametrize("gesture", (*SINGLE, Gesture.UNKNOWN))
@pytest.mark.parametrize("side", ["Left", "Right"])
@pytest.mark.parametrize("scale", [0.7, 1.0])
def test_static_gestures_and_unknown(gesture, side, scale):
    result = GestureClassifier().classify(sample(gesture, side, scale=scale))
    assert result.gesture == gesture
    assert result.quality == Quality.VALID


def test_none_is_not_unknown():
    assert GestureClassifier().classify(None).gesture == Gesture.NONE
    assert GestureClassifier().classify(sample(Gesture.UNKNOWN)).gesture == Gesture.UNKNOWN


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite(value):
    hand = sample()
    points = list(hand.landmarks)
    points[8] = HandPoint(value, 0.2, 0)
    invalid = replace(hand, landmarks=tuple(points))
    assert GestureClassifier().classify(invalid).gesture == Gesture.NONE


def test_zero_vectors_and_low_score():
    hand = sample()
    zero = replace(hand, landmarks=(HandPoint(0.5, 0.5, 0),) * 21)
    assert GestureClassifier().classify(zero).quality == Quality.INVALID
    assert GestureClassifier().classify(low_score(hand)).quality == Quality.LOW_CONFIDENCE


def test_aspect_ratio():
    hand = sample(Gesture.VICTORY)

    hand = replace(hand, landmarks=tuple(HandPoint(p.x / 2, p.y, p.z) for p in hand.landmarks))
    assert GestureClassifier().classify(hand, 200, 100).gesture == Gesture.VICTORY


def test_missing_landmarks_and_out_of_frame():
    hand = sample()
    assert GestureClassifier().classify(replace(hand, landmarks=())).gesture == Gesture.NONE
    assert GestureClassifier().classify(sample(dx=0.7)).quality == Quality.OUT_OF_FRAME


def test_thumb_direction_requires_vertical_view():
    hand = sample(Gesture.ROCK)

    assert GestureClassifier().classify(hand).gesture == Gesture.ROCK

