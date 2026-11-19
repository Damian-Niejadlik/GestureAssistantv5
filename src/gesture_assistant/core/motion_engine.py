from src.gesture_assistant.gestures.motion_classifier import MotionClassifier
from src.gesture_assistant.gestures.personal import palm_center


class MotionEngine:
    def __init__(self):
        self.classifier = MotionClassifier()

    def update(self, hand, gesture, timestamp_ms):
        position = palm_center(hand) if hand is not None else None
        return self.classifier.update(position, gesture, timestamp_ms)

