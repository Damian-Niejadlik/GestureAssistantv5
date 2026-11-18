from src.gesture_assistant.gestures.definitions import Gesture


class CooldownManager:
    def __init__(self):
        self._deadlines = {}

    def remaining(self, key, now_ms):
        return max(0, self._deadlines.get(key, 0) - now_ms)

    def start(self, key, now_ms, duration_ms):
        if duration_ms < 0:
            raise ValueError("Cooldown nie może być ujemny.")
        self._deadlines[key] = now_ms + duration_ms


class Debouncer:
    def __init__(self, frames=5, duration_ms=700, release_ms=1000, cooldown_ms=1000):
        if min(frames, duration_ms, release_ms, cooldown_ms) <= 0:
            raise ValueError("Progi debounce muszą być dodatnie.")
        self.frames = frames
        self.duration_ms = duration_ms
        self.release_ms = release_ms
        self.cooldown_ms = cooldown_ms
        self.cooldowns = CooldownManager()
        self._latched = {}
        self._absent = {}
        self._last = None
        self.reset_candidate()

    def reset_candidate(self):
        self._candidate = Gesture.NONE
        self._since = 0
        self._count = 0

    def tracking_discontinuity(self):
        """A missing time interval is not evidence of gesture release."""
        self.reset_candidate()
        self._absent.clear()

    def update(self, gesture, now_ms, allow_emit=True):
        if self._last is not None and now_ms <= self._last:
            raise ValueError("Timestampy debounce muszą rosnąć.")
        self._last = now_ms
        for old in list(self._latched):
            if old == gesture:
                self._absent.pop(old, None)
            else:
                self._absent.setdefault(old, now_ms)
                if now_ms - self._absent[old] >= self.release_ms:
                    del self._latched[old]
                    del self._absent[old]
        if gesture in (Gesture.NONE, Gesture.UNKNOWN):
            self.reset_candidate()
            return None
        if gesture != self._candidate:
            self._candidate, self._since, self._count = gesture, now_ms, 1
        else:
            self._count += 1
        stable = self._count >= self.frames or now_ms - self._since >= self.duration_ms
        if (
            stable
            and allow_emit
            and gesture not in self._latched
            and not self.cooldowns.remaining(gesture, now_ms)
        ):
            self._latched[gesture] = True
            self.cooldowns.start(gesture, now_ms, self.cooldown_ms)
            return gesture
        return None

