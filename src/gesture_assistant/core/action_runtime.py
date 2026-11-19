import logging
import threading
import time
from collections import deque

from src.gesture_assistant.config.schema import validate_config
from src.gesture_assistant.core.action_executor import ActionExecutor
from src.gesture_assistant.core.action_queue import ActionQueue
from src.gesture_assistant.core.config_manager import defaults
from src.gesture_assistant.core.context_detector import ContextDetector, clock_ms
from src.gesture_assistant.core.safety_manager import SafetyManager
from src.gesture_assistant.integrations import ACTION_CATALOG
from src.gesture_assistant.integrations.dispatcher import NativeDispatcher

logger = logging.getLogger(__name__)


class ActionRuntime:
    """One explicit lifecycle-managed action consumer; no work on GUI thread."""

    def __init__(self, config=None, detector=None, clock=clock_ms, backend=None):
        self._backend = backend
        self.safety = SafetyManager(defaults() if config is None else config, clock)
        self.detector = detector or ContextDetector(clock=clock)
        self.queue = ActionQueue()
        config = self.safety.config
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._last_outcome = None
        self._history = deque(maxlen=500)
        self._confirmation = None
        self.executor = ActionExecutor(
            self.safety,
            self.detector,
            dry_run=config["execution"]["dry_run"],
            dispatcher=NativeDispatcher(config, backend=self._backend),
            on_confirmation=self._need_confirmation,
        )

    def apply_config(self, config):
        with self._lock:
            self.pause()
            self.cancel_pending()
            self._config = validate_config(config)
            self.safety.update_config(self._config)
            self.executor.dry_run = self._config["execution"]["dry_run"]
            self.executor.dispatcher = NativeDispatcher(self._config, backend=self._backend)

    def active_gesture_signals(self):
        config = self.safety.config
        context = self.detector.detect(config["mode"])
        bindings = dict(config["profiles"].get(context.profile.value, {}))
        bindings.update(config["bindings"])
        return {signal for signal, action in bindings.items()
                if action in config["allowed_actions"]}

    def observe(self, analysis):
        observed = self.safety.observe(analysis)
        if not observed:
            self.cancel_pending()
        config = self.safety.config
        signal = analysis.motion_event.value if analysis.motion_event else analysis.gesture.value
        context = self.detector.detect(config["mode"])
        profile = config["profiles"].get(context.profile.value, {})
        bound = config["bindings"].get(signal)
        if bound is not None:
            action = None if bound == "none" else bound
            action_source = "Brak akcji (Globalne)" if bound == "none" else "Globalne"
        else:
            prof_bound = profile.get(signal)
            action = None if (prof_bound is None or prof_bound == "none") else prof_bound
            action_source = (
                f"Profil: {context.profile.value}" if action is not None else "Brak przypisania"
            )

        if getattr(analysis, "calibrated", False) and action and ACTION_CATALOG[action].destructive:
            action = None
            action_source = "Kalibracja nie uruchamia akcji wymagających potwierdzenia"

        with self._lock:
            self._latest_diagnostics = {
                "signal": signal,
                "gesture": analysis.gesture.value,
                "motion": analysis.motion.value,
                "motion_event": analysis.motion_event.value if analysis.motion_event else None,
                "quality": analysis.quality.value,
                "confidence": analysis.confidence,
                "mode": config["mode"],
                "active_profile": context.profile.value,
                "foreground_exe": context.foreground.executable if context.foreground else None,
                "foreground_pid": context.foreground.pid if context.foreground else None,
                "effective_action": action,
                "action_source": action_source,
                "paused": self.safety.paused,
                "enabled": config["safety"]["enabled"],
                "dry_run": self.executor.dry_run,
                "tracking_reason": self.safety.observation_reason,
                "stable_ms": self.safety.stable_ms,
                "required_hold_ms": config["thresholds"]["gesture_hold_ms"],
                "consumer_running": self.is_running,
                "reason": (
                    "paused"
                    if self.safety.paused
                    else (
                        "actions_disabled"
                        if not config["safety"]["enabled"]
                        else (
                            "no_binding"
                            if action is None
                            else (
                                self.safety.observation_reason
                                if not observed or self.safety.observation_reason
                                else self.safety.check_reason(action, signal, context)
                            )
                        )
                    )
                ),
            }

        if not observed or self.safety.paused or not config["safety"]["enabled"]:
            return
        with self._lock:
            pending = self._confirmation
            confirmation_signal = signal == "DOUBLE_THUMBS_UP"
            if pending is not None:
                action_id, target, deadline = pending
                now = self.safety.clock()
                if now >= deadline or context.identity != target.identity:
                    self._confirmation = None
                    return
                if observed and confirmation_signal:
                    request = self.safety.request_gesture_confirmation(
                        action_id, context, deadline - 15000, deadline,
                    )
                    if request is not None:
                        if self.queue.put(request):
                            self._confirmation = None
                        else:
                            self.safety.discard(request)
                return
            if confirmation_signal:
                return
        if action is None:
            return
        request = self.safety.request(action, signal, context)
        if request is not None and not self.queue.put(request):
            self.safety.discard(request)

    def set_dry_run(self, enabled):
        """A mode switch revokes queued capabilities and always requires explicit resume."""
        if type(enabled) is not bool:
            raise ValueError("dry_run musi być bool.")
        config = self.safety.config
        config["execution"]["dry_run"] = enabled
        self.apply_config(config)

    def diagnostics(self):
        with self._lock:
            diag = getattr(self, "_latest_diagnostics", None)
            return dict(diag) if diag is not None else None

    def cancel_pending(self):
        for request in self.queue.clear():
            self.safety.discard(request)

    def pause(self):
        self.safety.pause()
        self.cancel_pending()
        with self._lock:
            self._confirmation = None

    def resume(self):
        self.cancel_pending()
        self.safety.resume()

    def process_one(self):
        request = self.queue.pop()
        if request is None:
            return None
        outcome = self.executor.execute(request)
        with self._lock:
            self._last_outcome = outcome
            self._history.append((time.time(), outcome))
        return outcome

    def _need_confirmation(self, action_id, context):
        with self._lock:
            if not self._stop.is_set() and not self.safety.paused and self._confirmation is None:
                self._confirmation = (action_id, context, self.safety.clock() + 15000)

    def pending_confirmation(self):
        with self._lock:
            if self._confirmation and self.safety.clock() >= self._confirmation[2]:
                self._confirmation = None
            return None if self._confirmation is None else self._confirmation[:2]

    def confirm_pending(self):
        with self._lock:
            pending = self._confirmation
            self._confirmation = None
        if pending is None or self.safety.clock() >= pending[2] or self.safety.paused:
            return False
        self.safety.confirm_once(pending[0], pending[1])
        return True

    def history(self):
        with self._lock:
            return tuple(self._history)

    def clear_history(self):
        with self._lock:
            self._history.clear()

    def status(self):
        with self._lock:
            return self._last_outcome

    @property
    def is_running(self):
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Konsument akcji nadal działa.")
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="GestureActions", daemon=False)
            self._thread.start()

    def stop(self):
        self.pause()
        self._stop.set()

    def _run(self):
        try:
            while not self._stop.is_set():
                if self.queue.wait(0.1) and not self._stop.is_set():
                    self.process_one()
        except Exception:
            logger.exception("Konsument akcji zatrzymany po błędzie.")
            self.pause()
        finally:
            self.cancel_pending()

