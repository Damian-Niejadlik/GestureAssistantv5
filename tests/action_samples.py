from src.gesture_assistant.core.analysis_pipeline import AnalysisResult
from src.gesture_assistant.core.config_manager import defaults
from src.gesture_assistant.core.context_detector import ContextDetector, Foreground
from src.gesture_assistant.core.safety_manager import SafetyManager
from src.gesture_assistant.gestures.definitions import Gesture, Motion, Quality


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        return self.value


def analysis(stamp, gesture=Gesture.FIST, quality=Quality.VALID, motion=None):
    return AnalysisResult(
        stamp, gesture, motion or Motion.NONE, 0.85, quality, 0, "test", None, motion
    )


def policy(action="teams.toggle_mute"):
    config = defaults()
    config["safety"].update(enabled=True, paused=False)
    config["allowed_actions"] = [action]
    return config


def context(clock, executable="ms-teams.exe", hwnd=1):
    return ContextDetector(lambda: Foreground(hwnd, 42, "C:/Apps/" + executable), clock)


def ready(action="teams.toggle_mute", executable="ms-teams.exe", config=None):
    clock = Clock()
    safety = SafetyManager(policy(action) if config is None else config, clock)
    detector = context(clock, executable)
    feed(safety, clock, 0, 700)
    return safety, clock, detector


def feed(safety, clock, start, end, gesture=Gesture.FIST, quality=Quality.VALID):
    for stamp in range(start, end + 1, 100):
        clock.value = stamp
        safety.observe(analysis(stamp, gesture, quality))

