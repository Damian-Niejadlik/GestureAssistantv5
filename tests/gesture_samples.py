"""Synthetic geometry, not recordings or evidence of real-world accuracy."""

from dataclasses import replace

from src.gesture_assistant.gestures.definitions import Gesture
from src.gesture_assistant.vision.hand_provider import Hand, HandPoint, HandResult


def sample(gesture=Gesture.OPEN_PALM, side="Right", dx=0.0, dy=0.0, scale=1.0):
    p = [(0.5, 0.85, 0.0)] * 21
    fingers = ((5, 0.38, 0.62), (9, 0.5, 0.6), (13, 0.59, 0.62), (17, 0.69, 0.65))
    extended = {
        Gesture.OPEN_PALM: (True, True, True, True),
        Gesture.FIST: (False, False, False, False),
        Gesture.THUMBS_UP: (False, False, False, False),
        Gesture.THUMBS_DOWN: (False, False, False, False),
        Gesture.VICTORY: (True, True, False, False),
        Gesture.POINTING_UP: (True, False, False, False),
        Gesture.PINCH: (True, True, True, True),
        Gesture.ROCK: (False, False, False, True),
        Gesture.UNKNOWN: (True, False, True, False),
    }[gesture]
    for (index, x, y), is_extended in zip(fingers, extended, strict=True):
        if is_extended:
            coords = [(x, y), (x, y - 0.10), (x, y - 0.17), (x, y - 0.25)]
        else:
            coords = [(x, y), (x, y - 0.10), (x + 0.02, y + 0.03), (x + 0.01, y + 0.08)]
        p[index : index + 4] = [(a, b, 0.0) for a, b in coords]
    thumb = [(0.43, 0.76), (0.44, 0.70), (0.50, 0.72), (0.53, 0.74)]
    if gesture in (Gesture.OPEN_PALM, Gesture.ROCK):
        thumb = [(0.43, 0.76), (0.34, 0.70), (0.25, 0.65), (0.16, 0.60)]
    if gesture == Gesture.THUMBS_UP:
        thumb = [(0.42, 0.76), (0.38, 0.70), (0.38, 0.58), (0.38, 0.46)]
    if gesture == Gesture.THUMBS_DOWN:
        thumb = [(0.42, 0.70), (0.35, 0.73), (0.35, 0.85), (0.35, 0.98)]
    if gesture == Gesture.PINCH:
        thumb = [(0.43, 0.76), (0.32, 0.63), (0.30, 0.48), (0.38, 0.38)]
    p[1:5] = [(a, b, 0.0) for a, b in thumb]
    points = []
    for x, y, z in p:
        if side == "Left":
            x = 1 - x
        points.append(HandPoint((x - 0.5) * scale + 0.5 + dx, (y - 0.5) * scale + 0.5 + dy, z))
    return Hand(tuple(points), (), side, 0.99)


def frame(hand, timestamp_ms):
    return HandResult(timestamp_ms + 1, timestamp_ms, () if hand is None else (hand,))


def low_score(hand):
    return replace(hand, handedness_score=0.2)

