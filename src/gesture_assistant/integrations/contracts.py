from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ContextKind(str, Enum):
    UNKNOWN = "Unknown"
    TEAMS = "Teams"
    BROWSER = "Browser"
    PRESENTATION = "Presentation"
    MEDIA = "Media"
    SYSTEM = "System"


@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    context: ContextKind
    destructive: bool = False
    implemented: bool = False

    requires_target: bool = True


@dataclass(frozen=True)
class ActionOutcome:
    accepted: bool
    executed: bool
    reason: str
    action_id: str


class ActionHandler(Protocol):
    def __call__(self) -> None:
        """Perform one previously authorized action; no shell strings."""


class IntegrationNotImplemented(NotImplementedError):
    """Native integration intentionally unavailable in this stage."""


def unavailable():
    raise IntegrationNotImplemented("Integracja natywna nie jest zaimplementowana.")

