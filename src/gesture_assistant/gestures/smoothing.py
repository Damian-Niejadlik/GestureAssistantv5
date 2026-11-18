from dataclasses import replace

import numpy as np

from src.gesture_assistant.vision.hand_provider import HandPoint


class LandmarkSmoother:
    def __init__(self, alpha=0.65, max_gap_ms=250):
        if not 0 < alpha <= 1 or max_gap_ms <= 0:
            raise ValueError("Niepoprawne parametry EMA.")
        self.alpha = alpha
        self.max_gap_ms = max_gap_ms
        self.reset()

    def reset(self):
        self._points = None
        self._last = None
        self._side = None

    def update(self, hand, timestamp_ms):
        if hand is None:
            self.reset()
            return None
        points = np.array([(p.x, p.y, p.z) for p in hand.landmarks])
        if points.shape != (21, 3) or not np.isfinite(points).all():
            self.reset()
            return None
        if self._last is not None and timestamp_ms <= self._last:
            raise ValueError("Timestampy EMA muszą rosnąć.")
        if (
            self._points is None
            or timestamp_ms - self._last > self.max_gap_ms
            or self._side != hand.handedness
        ):
            self._points = points
        else:
            self._points = self.alpha * points + (1 - self.alpha) * self._points
        self._last = timestamp_ms
        self._side = hand.handedness
        return replace(hand, landmarks=tuple(HandPoint(*p) for p in self._points))

