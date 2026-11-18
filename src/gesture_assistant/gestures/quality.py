import numpy as np

from src.gesture_assistant.gestures.definitions import GestureConfig, Quality
from src.gesture_assistant.vision.hand_provider import Hand

NUMERICAL_EPSILON = 1e-8


def inspect_hand(hand: Hand | None, width: int, height: int, config: GestureConfig):
    """Validate raw points before smoothing. No invented visibility values."""
    if hand is None:
        return Quality.NO_HAND, None, 0.0
    if width <= 0 or height <= 0:
        raise ValueError("Wymiary obrazu muszą być dodatnie.")
    if len(hand.landmarks) != 21:
        return Quality.INVALID, None, 0.0
    points = np.array([(p.x, p.y, p.z) for p in hand.landmarks], dtype=float)
    if not np.isfinite(points).all():
        return Quality.INVALID, None, 0.0
    score = hand.handedness_score
    if (
        hand.handedness not in ("Left", "Right")
        or score is None
        or not np.isfinite(score)
        or not config.handedness_min <= score <= 1
    ):
        return Quality.LOW_CONFIDENCE, None, 0.0
    if ((points[:, :2] < 0) | (points[:, :2] > 1)).any():
        return Quality.OUT_OF_FRAME, None, 0.0

    xy = points[:, :2] * np.array([width, height]) / max(width, height)
    scale = np.linalg.norm(xy[9] - xy[0])
    palm_width = np.linalg.norm(xy[5] - xy[17])
    if min(scale, palm_width) < config.min_palm_size:
        return Quality.INVALID, None, 0.0
    if any(
        np.linalg.norm(xy[b] - xy[a]) < NUMERICAL_EPSILON
        for a, b in (
            (1, 2),
            (2, 3),
            (3, 4),
            (5, 6),
            (6, 7),
            (7, 8),
            (9, 10),
            (10, 11),
            (11, 12),
            (13, 14),
            (14, 15),
            (15, 16),
            (17, 18),
            (18, 19),
            (19, 20),
        )
    ):
        return Quality.INVALID, None, 0.0
    return Quality.VALID, (xy - xy[0]) / scale, float(score)

