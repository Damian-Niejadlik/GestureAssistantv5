import pytest

from src.gesture_assistant.integrations.keyboard_actions import validate_shortcut
from src.gesture_assistant.integrations.windows_actions import validate_application_path


@pytest.mark.parametrize("path", ["", "relative.exe", "C:/missing.exe", "app.exe --flag", 12])
def test_bad_application_path(path):
    with pytest.raises(ValueError):
        validate_application_path(path)


def test_existing_executable_path(tmp_path):
    exe = tmp_path / "test.exe"
    exe.write_bytes(b"not executed")
    assert validate_application_path(str(exe)) == exe.resolve()


@pytest.mark.parametrize("shortcut", ["ctrl++a", "ctrl+ctrl+a", "ctrl", "a+b", "win+l", "", 1])
def test_bad_shortcut(shortcut):
    with pytest.raises(ValueError):
        validate_shortcut(shortcut)


def test_good_shortcut():
    assert validate_shortcut("Ctrl + Shift + M") == ("ctrl", "shift", "m")

