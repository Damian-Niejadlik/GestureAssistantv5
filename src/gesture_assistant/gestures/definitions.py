from dataclasses import dataclass
from enum import Enum


class Gesture(str, Enum):
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"
    OPEN_PALM = "OPEN_PALM"
    FIST = "FIST"
    THUMBS_UP = "THUMBS_UP"
    THUMBS_DOWN = "THUMBS_DOWN"
    VICTORY = "VICTORY"
    POINTING_UP = "POINTING_UP"
    PINCH = "PINCH"
    ROCK = "ROCK"
    TRIANGLE = "TRIANGLE"
    DOUBLE_FIST = "DOUBLE_FIST"
    DOUBLE_THUMBS_UP = "DOUBLE_THUMBS_UP"


class Motion(str, Enum):
    NONE = "NONE"
    SWIPE_LEFT = "SWIPE_LEFT"
    SWIPE_RIGHT = "SWIPE_RIGHT"
    SWIPE_UP = "SWIPE_UP"
    SWIPE_DOWN = "SWIPE_DOWN"


class Quality(str, Enum):
    VALID = "VALID"
    NO_HAND = "NO_HAND"
    INVALID = "INVALID"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    OUT_OF_FRAME = "OUT_OF_FRAME"
    MULTIPLE_HANDS = "MULTIPLE_HANDS"


@dataclass(frozen=True)
class GestureConfig:

    handedness_min: float = 0.7
    confidence_cap: float = 0.85

    min_palm_size: float = 0.02
    extended_ratio: float = (
        0.84
    )
    folded_ratio: float = 0.76
    tip_reach: float = 1.02
    thumb_ratio: float = 0.80
    thumb_reach: float = 0.60
    pinch_distance: float = 0.25
    pinch_reach: float = 0.90
    spread_distance: float = 0.15
    vertical_dominance: float = 1.15
    ema_alpha: float = 0.65
    tracking_gap_ms: int = 250
    debounce_frames: int = 5
    debounce_ms: int = 700
    release_ms: int = 1000
    static_cooldown_ms: int = 1000


@dataclass(frozen=True)
class MotionConfig:
    distance: float = 0.25
    max_duration_ms: int = 700
    min_samples: int = 3
    dominance: float = 1.5
    efficiency: float = 0.85
    max_gap_ms: int = 250
    max_step: float = 0.35
    cooldown_ms: int = 1500
    max_samples: int = 240


@dataclass(frozen=True)
class Classification:
    gesture: Gesture
    confidence: float
    quality: Quality
    feedback: str

