import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from src.gesture_assistant.vision.hand_provider import MediaPipeHandProvider


def provider_with_sdk(tmp_path, monkeypatch):
    cv2 = ModuleType("cv2")
    cv2.COLOR_BGR2RGB = 1
    cv2.cvtColor = lambda frame, code: frame[:, :, ::-1].copy()
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    detector = SimpleNamespace(
        timestamps=[],
        closed=False,
    )

    def detect(image, timestamp):
        detector.timestamps.append(timestamp)
        return SimpleNamespace(hand_landmarks=[], handedness=[], hand_world_landmarks=[])

    def close():
        detector.closed = True

    detector.detect_for_video = detect
    detector.close = close
    mp = ModuleType("mediapipe")
    tasks = ModuleType("mediapipe.tasks")
    python = ModuleType("mediapipe.tasks.python")
    vision = ModuleType("mediapipe.tasks.python.vision")
    mp.Image = lambda **kwargs: kwargs
    mp.ImageFormat = SimpleNamespace(SRGB=1)
    python.BaseOptions = lambda **kwargs: kwargs
    vision.HandLandmarkerOptions = lambda **kwargs: kwargs
    vision.RunningMode = SimpleNamespace(VIDEO=1)
    vision.HandLandmarker = SimpleNamespace(create_from_options=lambda _: detector)
    mp.tasks, tasks.python, python.vision = tasks, python, vision
    for name, module in (
        ("mediapipe", mp),
        ("mediapipe.tasks", tasks),
        ("mediapipe.tasks.python", python),
        ("mediapipe.tasks.python.vision", vision),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    model = tmp_path / "fake.task"
    model.write_bytes(b"test-double-not-a-real-model")
    return MediaPipeHandProvider(model), detector


def test_strict_timestamps_and_close(tmp_path, monkeypatch):
    provider, detector = provider_with_sdk(tmp_path, monkeypatch)
    image = np.zeros((24, 32, 3), dtype=np.uint8)
    assert provider.process(image, 100).hands == ()
    for timestamp in (100, 99):
        with pytest.raises(ValueError, match="rosnące"):
            provider.process(image, timestamp)
    assert provider.process(image, 101).timestamp_ms == 101
    assert detector.timestamps == [100, 101]
    provider.close()
    provider.close()
    assert detector.closed
    with pytest.raises(RuntimeError):
        provider.process(image, 102)

