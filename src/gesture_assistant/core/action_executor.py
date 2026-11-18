import logging
import threading

from src.gesture_assistant.core.safety_manager import ActionRequest
from src.gesture_assistant.integrations import ACTION_CATALOG
from src.gesture_assistant.integrations.contracts import ActionOutcome

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Single-action admission with repeated native-operation authorization checks."""

    def __init__(
        self, safety, detector, handlers=None, dry_run=True, dispatcher=None, on_confirmation=None
    ):
        self.safety = safety
        self.detector = detector
        self.handlers = dict(handlers or {})
        if any(key not in ACTION_CATALOG for key in self.handlers):
            raise ValueError("Nieznana akcja handlera.")
        self.dry_run = dry_run
        self.dispatcher = dispatcher
        self.on_confirmation = on_confirmation
        self._lock = threading.Lock()

    def execute(self, request):
        if (
            not isinstance(request, ActionRequest)
            or not isinstance(request.token, str)
            or not request.token
        ):
            return ActionOutcome(False, False, "invalid_request", "")

        if not self._lock.acquire(blocking=False):
            self.safety.discard(request)
            return ActionOutcome(False, False, "busy", request.action_id)
        reserved = False
        try:
            context = self.detector.detect(self.safety.config["mode"])
            reason = self.safety.reserve(request, context)
            if reason:
                if reason == "explicit_confirmation_required" and self.on_confirmation is not None:
                    self.on_confirmation(request.action_id, context)
                return ActionOutcome(False, False, reason, request.action_id)
            reserved = True

            current = self.detector.detect(self.safety.config["mode"])
            if not self.safety.still_authorized(request, current):
                return ActionOutcome(False, False, "authorization_changed", request.action_id)
            if self.dry_run:
                return ActionOutcome(True, False, "dry_run_no_side_effect", request.action_id)

            def guard():
                latest = self.detector.detect(self.safety.config["mode"])
                return self.safety.still_authorized(request, latest)

            handler = self.handlers.get(request.action_id)
            if handler is not None:
                if not guard():
                    return ActionOutcome(False, False, "authorization_changed", request.action_id)
                result = handler()
            elif self.dispatcher is not None:
                result = self.dispatcher.dispatch(request, guard)
            else:
                return ActionOutcome(False, False, "not_implemented", request.action_id)
            reason = "executed" if result is None else f"executed: {result}"
            return ActionOutcome(True, True, reason, request.action_id)
        except Exception as exc:
            logger.exception("Action handler failed: %s", request.action_id)
            return ActionOutcome(False, False, f"handler_error: {exc}", request.action_id)
        finally:
            if reserved:
                self.safety.finish(request)
            self._lock.release()

