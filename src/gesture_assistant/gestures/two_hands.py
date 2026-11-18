from math import hypot

from src.gesture_assistant.gestures.definitions import Gesture


def classify_pair(first, second, labels, width, height):
    def distance(a, b):
        return hypot((a.x - b.x) * width, (a.y - b.y) * height)

    a, b = first.landmarks, second.landmarks
    scale = (distance(a[0], a[9]) + distance(b[0], b[9])) / 2
    if scale <= 0 or distance(a[0], b[0]) < 0.75 * scale:
        return Gesture.UNKNOWN
    if labels == (Gesture.FIST, Gesture.FIST) and distance(a[0], b[0]) < 4 * scale:
        return Gesture.DOUBLE_FIST
    if labels == (Gesture.THUMBS_UP, Gesture.THUMBS_UP):
        return Gesture.DOUBLE_THUMBS_UP
    if (distance(a[8], b[8]) < 0.24 * scale
            and distance(a[4], b[4]) < 0.24 * scale
            and a[4].y + b[4].y - a[8].y - b[8].y > 0.8 * scale / height
            and min(distance(a[4], a[8]), distance(b[4], b[8])) > 0.55 * scale):
        return Gesture.TRIANGLE
    return Gesture.UNKNOWN

