import math
from copy import deepcopy

from src.gesture_assistant.core.context_detector import MODES
from src.gesture_assistant.gestures.definitions import Gesture, Motion
from src.gesture_assistant.integrations import ACTION_CATALOG
from src.gesture_assistant.integrations.browser_actions import validate_url
from src.gesture_assistant.integrations.keyboard_actions import (
    validate_action_shortcut,
    validate_shortcut,
)
from src.gesture_assistant.integrations.windows_actions import validate_application_path

SCHEMA_VERSION = 1


class ConfigVersionError(ValueError):
    """Unknown schema must not be silently overwritten."""


def exact_keys(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(f"Niepoprawne pola konfiguracji, oczekiwano: {sorted(keys)}")


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Wymagany int w zakresie {low}..{high}.")


def boolean(value):
    if type(value) is not bool:
        raise ValueError("Wymagana wartość bool.")


def validate_config(value):
    if type(value) is not dict:
        raise ValueError("Konfiguracja musi być obiektem JSON.")
    value = deepcopy(value)
    value.setdefault("execution", {"dry_run": True})
    value.setdefault("profiles", {name: {} for name in MODES if name != "Auto"})
    exact_keys(
        value,
        (
            "schema_version",
            "mode",
            "camera",
            "preview",
            "feedback",
            "thresholds",
            "safety",
            "allowed_actions",
            "bindings",
            "targets",
            "execution",
            "profiles",
        ),
    )
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise ConfigVersionError("Nieobsługiwana wersja konfiguracji; plik nie zostanie nadpisany.")
    if value["mode"] not in MODES:
        raise ValueError("Nieznany tryb.")
    camera = value["camera"]
    exact_keys(camera, ("index", "fps_limit", "width", "height"))
    for key, low, high in (
        ("index", 0, 32),
        ("fps_limit", 5, 60),
        ("width", 320, 3840),
        ("height", 240, 2160),
    ):
        integer(camera[key], low, high)
    exact_keys(value["preview"], ("enabled", "landmarks"))
    exact_keys(value["feedback"], ("enabled",))
    for group in (value["preview"], value["feedback"]):
        for entry in group.values():
            boolean(entry)
    thresholds = value["thresholds"]
    required_threshold_keys = {
        "gesture_hold_ms",
        "action_cooldown_ms",
        "motion_cooldown_ms",
        "max_tracking_gap_ms",
        "max_event_age_ms",
        "min_confidence",
    }
    allowed_threshold_keys = required_threshold_keys | {
        "swipe_distance",
        "swipe_max_duration_ms",
    }
    if (
        type(thresholds) is not dict
        or not required_threshold_keys.issubset(set(thresholds))
        or not set(thresholds).issubset(allowed_threshold_keys)
    ):
        msg = f"Niepoprawne pola thresholds, oczekiwano: {sorted(required_threshold_keys)}"
        raise ValueError(msg)
    for key, low, high in (
        ("gesture_hold_ms", 700, 5000),
        ("action_cooldown_ms", 2000, 30000),
        ("motion_cooldown_ms", 1500, 30000),
        ("max_tracking_gap_ms", 1, 250),
        ("max_event_age_ms", 1, 250),
    ):
        integer(thresholds[key], low, high)
    if "swipe_distance" in thresholds:
        dist = thresholds["swipe_distance"]
        if type(dist) not in (int, float) or not math.isfinite(dist) or not 0.05 <= dist <= 0.8:
            raise ValueError("swipe_distance musi być liczbą w zakresie 0.05..0.8.")
    if "swipe_max_duration_ms" in thresholds:
        integer(thresholds["swipe_max_duration_ms"], 200, 3000)
    confidence = thresholds["min_confidence"]
    if (
        type(confidence) not in (int, float)
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        raise ValueError("Niepoprawny próg confidence.")
    safety = value["safety"]
    exact_keys(safety, ("paused", "enabled", "sleep_computer", "confirmed_destructive"))
    for key in ("paused", "enabled", "sleep_computer"):
        boolean(safety[key])
    for entries in (value["allowed_actions"], safety["confirmed_destructive"]):
        if type(entries) is not list or any(type(x) is not str for x in entries):
            raise ValueError("Wymagana lista identyfikatorów akcji.")
        if len(set(entries)) != len(entries) or any(x not in ACTION_CATALOG for x in entries):
            raise ValueError("Nieznana lub powtórzona akcja.")
    if any(not ACTION_CATALOG[x].destructive for x in safety["confirmed_destructive"]):
        raise ValueError("Lista potwierdzeń dotyczy wyłącznie akcji destrukcyjnych.")
    bindings = value["bindings"]
    signals = {g.value for g in Gesture if g not in (Gesture.NONE, Gesture.UNKNOWN)}
    signals.update(m.value for m in Motion if m != Motion.NONE)
    if type(bindings) is not dict or any(
        key not in signals
        or type(action) is not str
        or (action != "none" and action not in ACTION_CATALOG)
        for key, action in bindings.items()
    ):
        raise ValueError("Niepoprawne mapowanie gestu na akcję.")
    exact_keys(value["execution"], ("dry_run",))
    boolean(value["execution"]["dry_run"])
    exact_keys(value["profiles"], ("Teams", "Browser", "Presentation", "Media", "System"))
    for mode, profile in value["profiles"].items():
        if type(profile) is not dict or any(
            key not in signals
            or type(action) is not str
            or (
                action != "none"
                and (action not in ACTION_CATALOG or ACTION_CATALOG[action].context.value != mode)
            )
            for key, action in profile.items()
        ):
            raise ValueError("Niepoprawne mapowanie profilu.")
    exact_keys(value["targets"], ("applications", "urls", "shortcuts"))
    validators = {
        "applications": validate_application_path,
        "urls": validate_url,
        "shortcuts": validate_shortcut,
    }
    for name, validator in validators.items():
        targets = value["targets"][name]
        if type(targets) is not dict:
            raise ValueError("Cele muszą być słownikiem.")
        for key, target in targets.items():
            if type(key) is not str or not key or len(key) > 100:
                raise ValueError("Niepoprawna nazwa celu.")
            if name == "shortcuts":
                validate_action_shortcut(key, target)
            else:
                validator(target)
    return deepcopy(value)

