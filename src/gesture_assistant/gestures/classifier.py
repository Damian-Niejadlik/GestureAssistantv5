import numpy as np

from src.gesture_assistant.gestures.definitions import (
    Classification,
    Gesture,
    GestureConfig,
    Quality,
)
from src.gesture_assistant.gestures.quality import inspect_hand
from src.gesture_assistant.vision.hand_provider import Hand

NUMERICAL_EPSILON = 1e-8


def finger_state(points, indices, config: GestureConfig) -> tuple[str, float]:
    chain = points[list(indices)]
    length = np.linalg.norm(np.diff(chain, axis=0), axis=1).sum()
    ratio = np.linalg.norm(chain[-1] - chain[0]) / length
    reach = np.linalg.norm(chain[-1]) / max(np.linalg.norm(chain[1]), NUMERICAL_EPSILON)
    if ratio >= config.extended_ratio and reach >= config.tip_reach:
        margin = min(
            1.0, (ratio - config.extended_ratio) / 0.15 + (reach - config.tip_reach) / 0.20
        )
        return "extended", max(0.0, margin)
    if ratio <= config.folded_ratio or reach <= 1:
        margin = min(1.0, (config.folded_ratio - ratio) / 0.15)
        return "folded", max(0.0, margin)
    return "uncertain", 0.0


class GestureClassifier:
    def __init__(self, config: GestureConfig | None = None):
        self.config = config or GestureConfig()

    def classify(self, hand: Hand | None, width: int = 1, height: int = 1):
        c = self.config
        quality, p, score = inspect_hand(hand, width, height, c)
        if quality != Quality.VALID:
            return Classification(Gesture.NONE, 0.0, quality, quality.value)
        states = tuple(
            finger_state(p, ids, c)
            for ids in (
                (5, 6, 7, 8),
                (9, 10, 11, 12),
                (13, 14, 15, 16),
                (17, 18, 19, 20),
            )
        )
        thumb_path = np.linalg.norm(np.diff(p[1:5], axis=0), axis=1).sum()
        thumb = (
            np.linalg.norm(p[4] - p[1]) / thumb_path >= c.thumb_ratio
            and np.linalg.norm(p[4] - p[2]) >= c.thumb_reach
        )
        extended = tuple(s[0] == "extended" for s in states)
        folded = tuple(s[0] == "folded" for s in states)
        gesture = Gesture.UNKNOWN
        if (
            np.linalg.norm(p[4] - p[8]) <= c.pinch_distance
            and min(np.linalg.norm(p[4]), np.linalg.norm(p[8])) >= c.pinch_reach
        ):
            gesture = Gesture.PINCH
        elif all(folded):
            direction = p[4] - p[2]
            if thumb and abs(direction[1]) >= c.vertical_dominance * abs(direction[0]):
                gesture = Gesture.THUMBS_UP if direction[1] < 0 else Gesture.THUMBS_DOWN
            elif not thumb:
                gesture = Gesture.FIST
        elif (
            all(extended)
            and thumb
            and all(
                np.linalg.norm(p[a] - p[b]) >= c.spread_distance
                for a, b in ((8, 12), (12, 16), (16, 20))
            )
        ):
            gesture = Gesture.OPEN_PALM
        elif extended[:2] == (True, True) and all(folded[2:]) and not thumb:
            gesture = Gesture.VICTORY
        elif extended[0] and all(folded[1:]) and not thumb:
            gesture = Gesture.POINTING_UP
        elif all(folded[:3]) and extended[3] and thumb:

            gesture = Gesture.ROCK
        confidence = 0.0
        if gesture != Gesture.UNKNOWN:
            margins = [m for _, m in states]
            avg_margin = float(np.mean(margins)) if margins else 0.5
            confidence = min(c.confidence_cap, round(0.75 + 0.10 * avg_margin, 2))
        return Classification(gesture, confidence, quality, gesture.value)

