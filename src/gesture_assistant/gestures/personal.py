import math

from src.gesture_assistant.gestures.definitions import Gesture, Motion

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


PAIR = (Gesture.TRIANGLE, Gesture.DOUBLE_FIST, Gesture.DOUBLE_THUMBS_UP)
MOVES = tuple(m for m in Motion if m != Motion.NONE)


def pair_features(hands, width, height):
    if len(hands) != 2 or {h.handedness for h in hands} != {"Left", "Right"}:
        return None
    left, right = sorted(hands, key=lambda hand: hand.handedness)
    a, b = features(left, width, height), features(right, width, height)
    if a is None or b is None:
        return None
    l, r = left.landmarks[0], right.landmarks[0]
    return (*a, *b, r.x - l.x, r.y - l.y)


def valid_row(signal, row):
    if signal in SINGLE:
        return valid(row)
    if signal in PAIR:
        return (isinstance(row, (tuple, list)) and len(row) == 86
                and valid(row[:42]) and valid(row[42:84])
                and all(type(v) in (float, int) and -1 <= v <= 1 for v in row[84:]))
    return (signal in MOVES and isinstance(row, (tuple, list)) and len(row) == 2
            and all(type(v) in (int, float) and math.isfinite(v) for v in row)
            and 0.08 <= row[0] <= 1 and 100 <= row[1] <= 3000)


def match_pair(hands, width, height, samples):
    vector = pair_features(hands, width, height)
    if vector is None:
        return Gesture.UNKNOWN
    ranked = []
    for signal in PAIR:
        rows = samples.get(signal.value, ())
        if len(rows) != 10 or not all(valid_row(signal, row) for row in rows):
            continue
        scores = sorted(math.dist(vector[:84], row[:84]) / math.sqrt(84)
                        + math.dist(vector[84:], row[84:]) for row in rows)
        ranked.append((sum(scores[:3]) / 3, signal))
    ranked.sort(key=lambda item: item[0])
    if not ranked or ranked[0][0] > 0.14 or (len(ranked) > 1 and ranked[1][0] - ranked[0][0] < 0.06):
        return Gesture.UNKNOWN
    return ranked[0][1]


def palm_center(hand):
    points = [hand.landmarks[i] for i in (0, 5, 9, 13, 17)]
    return tuple(sum(getattr(point, axis) for point in points) / len(points) for axis in ("x", "y"))


def motion_sample(signal, trajectory):
    if signal not in MOVES or len(trajectory) < 3:
        return None
    times, points = zip(*trajectory)
    duration = times[-1] - times[0]
    steps = [math.dist(a, b) for a, b in zip(points, points[1:])]
    if (not 100 <= duration <= 3000 or max(steps) > 0.35
            or any(not 0 < b - a <= 250 for a, b in zip(times, times[1:]))):
        return None
    dx, dy = (points[-1][i] - points[0][i] for i in (0, 1))
    primary, cross = {Motion.SWIPE_LEFT: (-dx, dy), Motion.SWIPE_RIGHT: (dx, dy),
                      Motion.SWIPE_UP: (-dy, dx), Motion.SWIPE_DOWN: (dy, dx)}[signal]
    if primary < 0.08 or primary < 1.5 * abs(cross) or primary < 0.80 * sum(steps):
        return None
    row = (primary, duration)
    return row if valid_row(signal, row) else None


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

