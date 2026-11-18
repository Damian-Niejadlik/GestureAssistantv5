from src.gesture_assistant.core.debounce import Debouncer
from src.gesture_assistant.gestures.classifier import GestureClassifier
from src.gesture_assistant.gestures.definitions import GestureConfig


class GestureEngine:
    def __init__(self, config: GestureConfig | None = None):
        config = config or GestureConfig()
        self.classifier = GestureClassifier(config)
        self.debouncer = Debouncer(
            config.debounce_frames,
            config.debounce_ms,
            config.release_ms,
            config.static_cooldown_ms,
        )

