import math

from src.gesture_assistant.gestures.definitions import Gesture

SINGLE = tuple(g for g in Gesture if g.value in {
    "OPEN_PALM", "FIST", "THUMBS_UP", "THUMBS_DOWN", "VICTORY", "POINTING_UP", "PINCH", "ROCK",
})


def features(hand, width, height):
    if len(hand.landmarks) != 21:
        return None
    root = hand.landmarks[0]
    middle = hand.landmarks[9]
    scale = math.hypot((middle.x - root.x) * width, (middle.y - root.y) * height)
    if not math.isfinite(scale) or scale < 1:
        return None
    direction = -1 if hand.handedness == "Left" else 1
    values = tuple(value for point in hand.landmarks for value in (
        direction * (point.x - root.x) * width / scale,
        (point.y - root.y) * height / scale,
    ))
    return values if valid(values) else None


def valid(values):
    return isinstance(values, (tuple, list)) and len(values) == 42 and all(
        type(v) in (int, float) and math.isfinite(v) and abs(v) <= 10 for v in values
    )


def match(hand, width, height, samples):
    vector = features(hand, width, height)
    if vector is None:
        return Gesture.UNKNOWN
    ranked = []
    for gesture in SINGLE:
        rows = samples.get(gesture.value, ())
        if len(rows) != 10 or not all(valid(row) for row in rows):
            continue
        distances = sorted(math.dist(vector, row) / math.sqrt(42) for row in rows)
        ranked.append((sum(distances[:3]) / 3, gesture))
    ranked.sort(key=lambda item: item[0])
    if not ranked or ranked[0][0] > 0.14:
        return Gesture.UNKNOWN
    if len(ranked) > 1 and ranked[1][0] - ranked[0][0] < 0.06:
        return Gesture.UNKNOWN
    return ranked[0][1]

