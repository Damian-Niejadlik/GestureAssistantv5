import pytest

from src.gesture_assistant.core.context_detector import ContextDetector, Foreground
from src.gesture_assistant.integrations.contracts import ContextKind
from tests.action_samples import Clock, context


@pytest.mark.parametrize(
    "executable, expected",
    [
        ("ms-teams.exe", ContextKind.TEAMS),
        ("Teams.exe", ContextKind.TEAMS),
        ("chrome.exe", ContextKind.BROWSER),
        ("powerpnt.exe", ContextKind.PRESENTATION),
        ("spotify.exe", ContextKind.MEDIA),
        ("explorer.exe", ContextKind.SYSTEM),
        ("fake-teams.exe", ContextKind.SYSTEM),
    ],
)
def test_detect_exact_process(executable, expected):
    assert context(Clock(), executable).detect().kind == expected


def test_unknown_and_manual_mode_does_not_override_teams():
    c = Clock()
    assert ContextDetector(lambda: None, c).detect().kind == ContextKind.UNKNOWN
    snapshot = context(c).detect("System")
    assert snapshot.kind == ContextKind.TEAMS
    assert snapshot.system_blocked
    assert context(c, "chrome.exe").detect().system_blocked


def test_reader_failure_and_invalid_identity():
    def fail():
        raise OSError("permission denied")

    assert ContextDetector(fail).detect().kind == ContextKind.UNKNOWN
    invalid = ContextDetector(lambda: Foreground(0, 1, "ms-teams.exe")).detect()
    assert invalid.kind == ContextKind.UNKNOWN


@pytest.mark.parametrize(
    "executable, expected",
    [
        ("POWERPNT.EXE", ContextKind.PRESENTATION),
        ("vlc.exe", ContextKind.MEDIA),
        ("wmplayer.exe", ContextKind.MEDIA),
        ("msedgewebview2.exe", ContextKind.BROWSER),
    ],
)
def test_presentation_media_and_webview(executable, expected):
    assert context(Clock(), executable).detect().kind == expected


@pytest.mark.parametrize("path", ["relative.exe", "C:/Apps/", "C:/Apps/data.txt", "C:/A\x00.exe"])
def test_malformed_executable_is_not_system_fallback(path):
    snapshot = ContextDetector(lambda: Foreground(1, 42, path)).detect()
    assert snapshot.kind == ContextKind.UNKNOWN

