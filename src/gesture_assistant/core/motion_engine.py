from src.gesture_assistant.gestures.motion_classifier import MotionClassifier


class MotionEngine:
    def __init__(self):
        self.classifier = MotionClassifier()

    def update(self, hand, gesture, timestamp_ms):
        position = None
        if hand is not None:

            points = [hand.landmarks[i] for i in (0, 5, 9, 13, 17)]
            position = (
                sum(p.x for p in points) / len(points),
                sum(p.y for p in points) / len(points),
            )
        return self.classifier.update(position, gesture, timestamp_ms)

