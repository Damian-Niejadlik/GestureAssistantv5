from collections import deque
from statistics import median

import numpy as np

from src.gesture_assistant.core.debounce import CooldownManager
from src.gesture_assistant.gestures.definitions import Gesture, Motion, MotionConfig

from src.gesture_assistant.gestures.personal import MOVES, valid_row

CONFLICTING_STATIC_GESTURES = {
    Gesture.FIST,
    Gesture.PINCH,
    Gesture.THUMBS_UP,
    Gesture.THUMBS_DOWN,
    Gesture.ROCK,
    Gesture.VICTORY,
    Gesture.POINTING_UP,
}


class MotionClassifier:
    def __init__(self, config: MotionConfig | None = None):
        self.config = config or MotionConfig()
        self.cooldowns = CooldownManager()
        self._last = None
        self.samples = {}
        self.reset()

    def reset(self):
        self._history = deque(maxlen=self.config.max_samples)

    def update(self, position, gesture, timestamp_ms):
        if self._last is not None and timestamp_ms <= self._last:
            raise ValueError("Timestampy ruchu muszą rosnąć.")
        self._last = timestamp_ms
        c = self.config
        if position is None or gesture in CONFLICTING_STATIC_GESTURES or gesture == Gesture.NONE:
            self.reset()
            return Motion.NONE
        point = np.asarray(position, dtype=float)
        if point.shape != (2,) or not np.isfinite(point).all():
            self.reset()
            return Motion.NONE
        if self.cooldowns.remaining("motion", timestamp_ms):
            self.reset()
            return Motion.NONE
        if self._history:
            last_t, last_p, _ = self._history[-1]
            if timestamp_ms - last_t > c.max_gap_ms:
                self.reset()
            elif np.linalg.norm(point - last_p) > c.max_step:
                self.reset()
        self._history.append((timestamp_ms, point, gesture))
        limits = {}
        for signal in MOVES:
            rows = self.samples.get(signal.value, ())
            if len(rows) == 10 and all(valid_row(signal, row) for row in rows):
                limits[signal] = (max(0.08, median(row[0] for row in rows) * 0.8),
                                  min(3000, max(200, median(row[1] for row in rows) * 1.25)))
        window = max([c.max_duration_ms, *(duration for _, duration in limits.values())])
        while self._history and timestamp_ms - self._history[0][0] > window:
            self._history.popleft()
        if len(self._history) < c.min_samples:
            return Motion.NONE
        if not any(g == Gesture.OPEN_PALM for _, _, g in self._history):
            return Motion.NONE
        for duration in sorted({c.max_duration_ms, *(d for _, d in limits.values())}):
            motion = self._classify_window(timestamp_ms, duration, limits)
            if motion != Motion.NONE:
                self.cooldowns.start("motion", timestamp_ms, c.cooldown_ms)
                self.reset()
                return motion
        return Motion.NONE

    def _classify_window(self, now, duration, limits):
        c = self.config
        recent = [(p, g) for t, p, g in self._history if now - t <= duration]
        if len(recent) < c.min_samples or not any(g == Gesture.OPEN_PALM for _, g in recent):
            return Motion.NONE
        points = np.array([p for p, _ in recent])
        start_idx = 0
        while start_idx < len(points) - c.min_samples:
            if np.linalg.norm(points[start_idx + 1] - points[0]) > 0.04:
                break
            start_idx += 1
        active = points[start_idx:]
        if len(active) < c.min_samples:
            return Motion.NONE
        delta = active[-1] - active[0]
        axis = int(np.argmax(np.abs(delta)))
        if abs(delta[axis]) < c.dominance * abs(delta[1 - axis]):
            return Motion.NONE
        length = np.linalg.norm(np.diff(active, axis=0), axis=1).sum()
        if length == 0 or np.linalg.norm(delta) / length < c.efficiency:
            return Motion.NONE
        motion = (
            (Motion.SWIPE_LEFT if delta[0] < 0 else Motion.SWIPE_RIGHT)
            if axis == 0
            else (Motion.SWIPE_UP if delta[1] < 0 else Motion.SWIPE_DOWN)
        )
        distance, allowed_duration = limits.get(motion, (c.distance, c.max_duration_ms))
        if duration != allowed_duration or abs(delta[axis]) < distance:
            return Motion.NONE
        return motion

