from dataclasses import replace

import pytest

from src.gesture_assistant.core.analysis_pipeline import AnalysisPipeline
from src.gesture_assistant.gestures.definitions import Gesture, Motion, Quality
from tests.gesture_samples import frame, low_score, sample


def test_fist_event_and_no_repeat():
    p = AnalysisPipeline()
    events = [
        p.process(frame(sample(Gesture.FIST), i * 50), 100, 100).gesture_event for i in range(10)
    ]
    assert events.count(Gesture.FIST) == 1


def test_loss_low_quality_multiple():
    p = AnalysisPipeline()
    assert p.process(frame(None, 0), 100, 100).gesture == Gesture.NONE
    assert p.process(frame(low_score(sample()), 10), 100, 100).quality == Quality.LOW_CONFIDENCE
    two = replace(frame(sample(), 20), hands=(sample(), sample(side="Left")))
    result = p.process(two, 100, 100)
    assert result.quality == Quality.MULTIPLE_HANDS
    assert result.gesture_event is None
    assert result.motion == Motion.NONE


def test_swipe_pipeline_and_no_static_event_during_motion_cooldown():
    p = AnalysisPipeline()
    results = [
        p.process(frame(sample(scale=0.5, dx=-0.2 + i * 0.1), i * 100), 100, 100) for i in range(4)
    ]
    assert results[-1].motion_event == Motion.SWIPE_RIGHT
    assert results[-1].gesture_event is None
    assert results[-1].cooldown_ms == 1500


def test_gap_side_switch_and_timestamp():
    p = AnalysisPipeline()
    p.process(frame(sample(), 0), 100, 100)
    result = p.process(frame(sample(side="Left"), 1000), 100, 100)
    assert result.motion == Motion.NONE
    assert result.gesture_event is None
    with pytest.raises(ValueError):
        p.process(frame(sample(), 1000), 100, 100)

