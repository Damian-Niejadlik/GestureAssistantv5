from dataclasses import dataclass

from src.gesture_assistant.core.gesture_engine import GestureEngine
from src.gesture_assistant.core.motion_engine import MotionEngine
from src.gesture_assistant.gestures.definitions import (
    Gesture,
    GestureConfig,
    Motion,
    MotionConfig,
    Quality,
)
from src.gesture_assistant.gestures.personal import match, match_pair
from src.gesture_assistant.gestures.two_hands import classify_pair
from src.gesture_assistant.gestures.quality import inspect_hand
from src.gesture_assistant.gestures.smoothing import LandmarkSmoother


@dataclass(frozen=True)
class AnalysisResult:
    timestamp_ms: int
    gesture: Gesture
    motion: Motion
    confidence: float
    quality: Quality
    cooldown_ms: int
    feedback: str
    gesture_event: Gesture | None
    motion_event: Motion | None
    tracking_epoch: int = 0
    calibrated: bool = False


class AnalysisPipeline:
    """Select one unambiguous command without carrying hold between hands."""

    def __init__(self, config: GestureConfig | None = None):
        self.config = config or GestureConfig()
        self.gestures = GestureEngine(self.config)
        self.motions = MotionEngine()
        self.smoother = LandmarkSmoother(
            self.config.ema_alpha,
            self.config.tracking_gap_ms,
        )
        self._last = None
        self._side = None
        self._wrist = None
        self._tracking_epoch = 0
        self._pair_wrists = {}
        self._was_calibrated = False
        self.samples = {}
        self.active_signals = lambda: set()

    def process(self, result, width, height):
        now = result.timestamp_ms
        if type(now) is not int or now < 0:
            raise ValueError("Timestamp musi być nieujemnym int.")
        if self._last is not None and now <= self._last:
            raise ValueError("Timestampy pipeline muszą rosnąć.")
        gap = self._last is not None and now - self._last > self.config.tracking_gap_ms
        self._last = now
        hand = result.hands[0] if len(result.hands) == 1 else None
        quality, _, _ = inspect_hand(hand, width, height, self.config)
        pair = Gesture.UNKNOWN
        calibrated = False
        if len(result.hands) > 1:
            candidates = [item for item in result.hands
                          if inspect_hand(item, width, height, self.config)[0] == Quality.VALID]
            quality = Quality.MULTIPLE_HANDS
            if len(result.hands) == 2 and len(candidates) == 2 and (
                candidates[0].handedness != candidates[1].handedness
            ):
                labels = tuple(self.gestures.classifier.classify(item, width, height).gesture
                               for item in candidates)
                pair = classify_pair(*candidates, labels, width, height)
                if pair == Gesture.UNKNOWN and self.samples:
                    pair = match_pair(candidates, width, height, self.samples)
                    calibrated = pair != Gesture.UNKNOWN
                if pair == Gesture.UNKNOWN:
                    signals = self.active_signals()
                    selected = [item for item, gesture in zip(candidates, labels)
                                if gesture.value in signals]
                    if not selected:
                        selected = [item for item, gesture in zip(candidates, labels)
                                    if gesture != Gesture.UNKNOWN]
                    if len(selected) == 1:
                        hand, quality = selected[0], Quality.VALID
            elif len(result.hands) == 2 and len(candidates) == 1:
                hand, quality = candidates[0], Quality.VALID
        if pair != Gesture.UNKNOWN:
            quality = Quality.VALID
        side = "pair" if pair != Gesture.UNKNOWN else hand.handedness if hand else None
        switch = side is not None and self._side not in (None, side)
        if hand is not None and self._wrist is not None:
            wrist = hand.landmarks[0] if hand.landmarks else None
            if wrist is not None:
                switch = (
                    switch
                    or ((wrist.x - self._wrist.x) ** 2 + (wrist.y - self._wrist.y) ** 2) ** 0.5
                    > self.motions.classifier.config.max_step
                )
        pair_wrists = ({item.handedness: item.landmarks[0] for item in candidates}
                       if pair != Gesture.UNKNOWN else {})
        for name, wrist in pair_wrists.items():
            previous = self._pair_wrists.get(name)
            if previous is not None and ((wrist.x - previous.x) ** 2 +
                                         (wrist.y - previous.y) ** 2) ** 0.5 > (
                self.motions.classifier.config.max_step
            ):
                switch = True
        self._pair_wrists = pair_wrists
        if gap or switch:
            self.gestures.debouncer.tracking_discontinuity()
        if gap or switch or quality != Quality.VALID:
            self._tracking_epoch += 1
            self.smoother.reset()
            self.motions.classifier.reset()
            self.gestures.debouncer.reset_candidate()
        if pair != Gesture.UNKNOWN:
            self._side, self._wrist = side, None
            gesture, confidence, motion = pair, 0.80, Motion.NONE
            self.motions.update(None, Gesture.NONE, now)
        elif quality == Quality.VALID:
            self._side = hand.handedness
            self._wrist = hand.landmarks[0]
            smoothed = self.smoother.update(hand, now)
            classification = self.gestures.classifier.classify(smoothed, width, height)
            raw = self.gestures.classifier.classify(hand, width, height)
            if classification.gesture == raw.gesture:
                gesture = classification.gesture
            elif raw.gesture == Gesture.UNKNOWN:
                gesture = classification.gesture
            elif classification.gesture == Gesture.UNKNOWN:
                gesture = raw.gesture
            else:
                gesture = Gesture.UNKNOWN

            if classification.gesture == Gesture.OPEN_PALM or raw.gesture == Gesture.OPEN_PALM:
                gate = Gesture.OPEN_PALM
            elif any(
                g
                in (
                    Gesture.FIST,
                    Gesture.PINCH,
                    Gesture.THUMBS_UP,
                    Gesture.THUMBS_DOWN,
                    Gesture.ROCK,
                    Gesture.VICTORY,
                    Gesture.POINTING_UP,
                )
                for g in (raw.gesture, classification.gesture)
            ):
                gate = raw.gesture if raw.gesture != Gesture.UNKNOWN else classification.gesture
            else:
                gate = Gesture.UNKNOWN

            self.motions.classifier.samples = self.samples
            motion = self.motions.update(hand, gate, now)
            confidence = (
                0.0
                if gesture == Gesture.UNKNOWN
                else classification.confidence
                if gesture == classification.gesture
                else raw.confidence
            )
            if gesture == Gesture.UNKNOWN and raw.gesture == classification.gesture and self.samples:
                gesture = match(hand, width, height, self.samples)
                calibrated = gesture != Gesture.UNKNOWN
                confidence = 0.76 if calibrated else 0.0
        else:
            self._side, self._wrist = None, None
            gesture, motion, confidence = Gesture.NONE, Motion.NONE, 0.0
            self.motions.update(None, Gesture.NONE, now)
        if calibrated != self._was_calibrated:
            self._tracking_epoch += 1
            self.gestures.debouncer.tracking_discontinuity()
        self._was_calibrated = calibrated
        cooldown = self.motions.classifier.cooldowns.remaining("motion", now)
        event = self.gestures.debouncer.update(gesture, now, allow_emit=cooldown == 0)
        static_cd = self.gestures.debouncer.cooldowns.remaining(gesture, now)
        feedback = (
            "Dwie dłonie: brak jednej jednoznacznej komendy"
            if quality == Quality.MULTIPLE_HANDS
            else "Niewiarygodne dane lub brak dłoni"
            if quality != Quality.VALID
            else "Gest nieznany"
            if gesture == Gesture.UNKNOWN
            else "Zdarzenie ruchu"
            if motion != Motion.NONE
            else "Zwolnij gest na 1 s przed ponowieniem"
            if event
            else "Śledzenie"
        )
        return AnalysisResult(
            now,
            gesture,
            motion,
            confidence,
            quality,
            max(cooldown, static_cd),
            feedback,
            event,
            motion if motion != Motion.NONE else None,
            self._tracking_epoch,
            calibrated,
        )

    def apply_config(self, config: dict):
        thresholds = config.get("thresholds", {})
        if "gesture_hold_ms" in thresholds:
            self.gestures.debouncer.duration_ms = thresholds["gesture_hold_ms"]
        m_cfg = self.motions.classifier.config
        new_distance = thresholds.get("swipe_distance", m_cfg.distance)
        new_duration = thresholds.get("swipe_max_duration_ms", m_cfg.max_duration_ms)
        new_cooldown = thresholds.get("motion_cooldown_ms", m_cfg.cooldown_ms)
        self.motions.classifier.config = MotionConfig(
            distance=new_distance,
            max_duration_ms=new_duration,
            min_samples=m_cfg.min_samples,
            dominance=m_cfg.dominance,
            efficiency=m_cfg.efficiency,
            max_gap_ms=m_cfg.max_gap_ms,
            max_step=m_cfg.max_step,
            cooldown_ms=new_cooldown,
            max_samples=m_cfg.max_samples,
        )

