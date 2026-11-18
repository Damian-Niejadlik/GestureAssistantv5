import math
import threading
import uuid
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass

from src.gesture_assistant.config.schema import validate_config
from src.gesture_assistant.core.context_detector import clock_ms
from src.gesture_assistant.gestures.definitions import Gesture, Motion, Quality
from src.gesture_assistant.integrations import ACTION_CATALOG
from src.gesture_assistant.integrations.contracts import ContextKind

from src.gesture_assistant.integrations.media_actions import (
    DEFAULT_SHORTCUTS as MEDIA_SHORTCUTS,
)


@dataclass(frozen=True)
class ActionRequest:
    token: str
    action_id: str
    signal: str
    captured_ms: int
    generation: int
    context_identity: object
    is_motion: bool


class SafetyManager:
    """Authoritative admission state. Requests are short-lived, one-use capabilities."""

    def __init__(self, config, clock=clock_ms):
        self._config = validate_config(config)
        self.clock = clock
        self._lock = threading.RLock()
        self._paused = self._config["safety"]["paused"]
        self._generation = 0
        self._issued = OrderedDict()
        self._active = None
        self._action_until = 0
        self._motion_until = 0
        self._last_motion = None
        self._last = None
        self._last_input = None
        self._tracking_epoch = None
        self._gesture = Gesture.NONE
        self._since = None
        self._latched = set()
        self._absent = {}
        self._confirmations = {}
        self._observation_reason = "stale_tracking"

    @property
    def config(self):
        return deepcopy(self._config)

    @property
    def paused(self):
        with self._lock:
            return self._paused

    @property
    def observation_reason(self):
        with self._lock:
            return self._observation_reason

    @property
    def stable_ms(self):
        with self._lock:
            if self._since is None or self._last is None:
                return 0
            return max(0, self._last - self._since)

    def pause(self):
        with self._lock:
            self._paused = True
            self._invalidate()

    def resume(self):
        with self._lock:
            self._paused = False
            self._invalidate()

    def _invalidate(self):
        self._generation += 1
        self._issued.clear()
        self._confirmations.clear()
        self._gesture = Gesture.NONE
        self._since = None
        self._last = None

    def observe(self, analysis):
        with self._lock:
            now = self.clock()
            thresholds = self._config["thresholds"]
            stamp = analysis.timestamp_ms
            timely = (
                type(stamp) is int
                and 0 <= now - stamp <= thresholds["max_event_age_ms"]
                and (self._last_input is None or stamp > self._last_input)
            )
            if not timely:
                if type(stamp) is not int:
                    self._observation_reason = "invalid_tracking_timestamp"
                elif stamp > now:
                    self._observation_reason = "future_tracking"
                elif now - stamp > thresholds["max_event_age_ms"]:
                    self._observation_reason = "stale_tracking"
                else:
                    self._observation_reason = "non_monotonic_tracking"
                self._invalidate()
                self._absent.clear()
                return False
            if (
                self._last_input is None
                or stamp - self._last_input > thresholds["max_tracking_gap_ms"]
            ):
                self._absent.clear()
            self._last_input = stamp
            epoch = analysis.tracking_epoch
            if self._tracking_epoch is not None and epoch != self._tracking_epoch:
                self._invalidate()
                self._absent.clear()
            self._tracking_epoch = epoch
            age_limit = thresholds["max_event_age_ms"]
            if not (
                type(stamp) is int
                and 0 <= now - stamp <= age_limit
                and (self._last is None or stamp > self._last)
            ):
                self._observation_reason = "non_monotonic_tracking"
                self._invalidate()
                return False
            if analysis.quality != Quality.VALID:
                self._observation_reason = "tracking_quality_" + analysis.quality.value.lower()
                self._invalidate()
                if analysis.quality == Quality.NO_HAND:
                    self._release_latches(None, stamp)
                else:
                    self._absent.clear()
                return False

            self._observation_reason = ""
            has_motion = analysis.motion_event not in (None, Motion.NONE)
            if has_motion:
                self._last = stamp
                self._last_motion = (analysis.motion_event.value, stamp)
                self._motion_until = now + thresholds["motion_cooldown_ms"]
                if analysis.gesture not in (Gesture.NONE, Gesture.UNKNOWN):
                    self._gesture = analysis.gesture
                return True

            is_valid_static = (
                analysis.gesture not in (Gesture.NONE, Gesture.UNKNOWN)
                and type(analysis.confidence) in (int, float)
                and math.isfinite(analysis.confidence)
                and thresholds["min_confidence"] <= analysis.confidence <= 1
            )
            if is_valid_static:
                continuous = (
                    self._last is not None
                    and stamp - self._last <= thresholds["max_tracking_gap_ms"]
                )
                if not continuous or self._gesture != analysis.gesture:
                    self._generation += 1
                    self._issued.clear()
                    self._since = stamp
                self._release_latches(analysis.gesture.value, stamp)
                self._last = stamp
                self._gesture = analysis.gesture
                return True

            self._observation_reason = (
                "gesture_unknown"
                if analysis.gesture in (Gesture.NONE, Gesture.UNKNOWN)
                else "low_confidence"
            )



            self._last = stamp
            if self._gesture not in (Gesture.NONE, Gesture.UNKNOWN):
                if self._since is not None and stamp - self._since > 150:
                    self._gesture = Gesture.UNKNOWN
                    self._since = None
            return True

    def _release_latches(self, signal, stamp):
        for old in list(self._latched):
            if old == signal:
                self._absent.pop(old, None)
            else:
                self._absent.setdefault(old, stamp)
                if stamp - self._absent[old] >= 1000:
                    self._latched.remove(old)
                    self._absent.pop(old, None)

    def confirm_once(self, action_id, context):
        """Explicit UI confirmation, never inferred from another gesture."""
        with self._lock:
            if action_id not in ACTION_CATALOG or not ACTION_CATALOG[action_id].destructive:
                raise ValueError("Potwierdzenie dotyczy znanej akcji destrukcyjnej.")
            self._invalidate()
            self._confirmations[action_id] = (context.identity, self.clock() + 5000)

    def _context_reason(self, action, context, now):
        if not 0 <= now - context.observed_ms <= 250 or context.foreground is None:
            return "unknown_or_stale_context"
        native_volume_key = {
            "media.volume_up": "volume_up",
            "media.volume_down": "volume_down",
        }.get(action.action_id)

        uses_native_volume_key = (
                native_volume_key is not None
                and self._config["targets"]["shortcuts"]
                .get(action.action_id, MEDIA_SHORTCUTS[action.action_id])
                .strip()
                .lower()
                == native_volume_key
        )

        if not action.requires_target or (
                uses_native_volume_key and context.is_own_process
        ):


            if context.kind == ContextKind.UNKNOWN and not context.is_own_process:
                return "unknown_or_stale_context"
            return ""
        if context.is_own_process:
            return "assistant_window_not_target"
        if action.context == ContextKind.SYSTEM and context.system_blocked:
            return "system_blocked_in_teams_browser_or_unknown"
        if context.kind == ContextKind.UNKNOWN or context.profile != action.context:
            return "wrong_context"
        if action.context != ContextKind.SYSTEM and context.kind != action.context:
            return "wrong_target_application"
        mode = self._config["mode"]
        if mode != "Auto" and mode != action.context.value:
            return "wrong_mode"
        return ""

    def update_config(self, config):
        with self._lock:
            self._config = validate_config(config)
            self._invalidate()

    def request_gesture_confirmation(self, action_id, context, opened_at, deadline):
        with self._lock:
            now = self.clock()
            signal = Gesture.DOUBLE_THUMBS_UP.value
            if (now >= deadline or self._since is None or self._since < opened_at
                    or self._last is None or self._last - self._since < 2000
                    or self._gesture.value != signal):
                return None
            request = self.request(action_id, signal, context)
            if request is not None:
                self._confirmations[action_id] = (context.identity, deadline)
            return request

    def request(self, action_id, signal, context):
        with self._lock:
            now = self.clock()
            if type(signal) is not str:
                return None
            is_motion = signal in {m.value for m in Motion if m != Motion.NONE}
            if self._base_reason(action_id, context, now, is_motion=is_motion):
                return None
            if is_motion:
                if self._last_motion != (signal, self._last):
                    return None
            elif signal != self._gesture.value or signal in self._latched:
                return None
            elif now < self._motion_until:
                return None
            if any(r.signal == signal for r in self._issued.values()):
                return None
            request = ActionRequest(
                uuid.uuid4().hex,
                action_id,
                signal,
                self._last,
                self._generation,
                context.identity,
                is_motion,
            )
            while len(self._issued) >= 64:
                self._issued.popitem(last=False)
            self._issued[request.token] = request
            return request

    def check_reason(self, action_id, signal, context):
        with self._lock:
            now = self.clock()
            if type(signal) is not str:
                return "invalid_signal"
            is_motion = signal in {m.value for m in Motion if m != Motion.NONE}
            base = self._base_reason(action_id, context, now, is_motion=is_motion)
            if base:
                return base
            if is_motion:
                if self._last_motion != (signal, self._last):
                    return "motion_changed"
            elif signal != self._gesture.value:
                return "gesture_changed"
            elif signal in self._latched:
                return "gesture_latched"
            elif now < self._motion_until:
                return "motion_cooldown"
            return ""

    def _base_reason(self, action_id, context, now, is_motion=False):
        policy = self._config["safety"]
        t = self._config["thresholds"]
        if self._paused:
            return "paused"
        if not policy["enabled"]:
            return "actions_disabled"
        if (
            type(action_id) is not str
            or action_id not in ACTION_CATALOG
            or action_id not in self._config["allowed_actions"]
        ):
            return "action_not_allowed"
        if action_id == "sleep_computer" and not policy["sleep_computer"]:
            return "sleep_disabled"
        if self._last is None or not 0 <= now - self._last <= t["max_event_age_ms"]:
            return "stale_tracking"
        if not is_motion and (
            self._since is None or self._last - self._since < t["gesture_hold_ms"]
        ):
            return "gesture_not_stable_700ms"
        if self._active is not None:
            return "busy"
        if now < self._action_until:
            return "action_cooldown"
        return self._context_reason(ACTION_CATALOG[action_id], context, now)

    def reserve(self, request, context):
        if (
            not isinstance(request, ActionRequest)
            or not isinstance(request.token, str)
            or not request.token
        ):
            return "invalid_request"

        with self._lock:
            now = self.clock()
            issued = self._issued.pop(request.token, None)
            if issued != request:
                return "invalid_or_consumed_request"
            reason = self._base_reason(request.action_id, context, now, is_motion=request.is_motion)
            if reason:
                return reason
            if (
                request.generation != self._generation
                or request.context_identity != context.identity
            ):
                return "tracking_or_context_changed"
            if not 0 <= now - request.captured_ms <= self._config["thresholds"]["max_event_age_ms"]:
                return "expired_request"
            if request.is_motion:
                if self._last_motion != (request.signal, request.captured_ms):
                    return "motion_changed"
            elif now < self._motion_until:
                return "motion_cooldown"
            if not request.is_motion and request.signal != self._gesture.value:
                return "gesture_changed"
            action = ACTION_CATALOG[request.action_id]
            if action.destructive:
                if request.signal == Gesture.DOUBLE_THUMBS_UP.value and (
                    self._since is None or self._last - self._since < 2000
                ):
                    return "gesture_not_stable_700ms"
                if request.action_id not in self._config["safety"]["confirmed_destructive"]:
                    return "destructive_not_enabled_in_settings"
                confirmation = self._confirmations.pop(request.action_id, None)
                if (
                    confirmation is None
                    or confirmation[0] != context.identity
                    or now >= confirmation[1]
                ):
                    return "explicit_confirmation_required"
            self._active = request.token
            if not request.is_motion:
                self._latched.add(request.signal)
            return ""

    def still_authorized(self, request, context):
        with self._lock:
            now = self.clock()
            return (
                self._active == request.token
                and not self._paused
                and self._last is not None
                and 0 <= now - self._last <= self._config["thresholds"]["max_event_age_ms"]
                and 0 <= now - request.captured_ms <= self._config["thresholds"]["max_event_age_ms"]
                and request.generation == self._generation
                and context.identity == request.context_identity
                and not self._context_reason(ACTION_CATALOG[request.action_id], context, now)
            )

    def finish(self, request):
        with self._lock:
            if self._active == request.token:
                self._active = None
                self._action_until = self.clock() + self._config["thresholds"]["action_cooldown_ms"]

    def discard(self, request):
        with self._lock:
            self._issued.pop(request.token, None)

