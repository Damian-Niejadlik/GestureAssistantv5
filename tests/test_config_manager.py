import json
from unittest.mock import patch

import pytest

from src.gesture_assistant.config.schema import ConfigVersionError, validate_config
from src.gesture_assistant.core.config_manager import ConfigManager, defaults


@pytest.mark.parametrize(
    "section, key, bad",
    [
        ("camera", "index", True),
        ("camera", "fps_limit", 0),
        ("camera", "width", "1280"),
        ("thresholds", "gesture_hold_ms", 699),
        ("thresholds", "action_cooldown_ms", 1999),
        ("thresholds", "motion_cooldown_ms", 1499),
        ("thresholds", "min_confidence", float("nan")),
        ("safety", "paused", 1),
    ],
)
def test_strict_validation(section, key, bad):
    config = defaults()
    config[section][key] = bad
    with pytest.raises(ValueError):
        validate_config(config)


def test_defaults_and_roundtrip(tmp_path):
    manager = ConfigManager(tmp_path / "config.json")
    config = manager.load().config
    assert config["safety"]["paused"] and not config["safety"]["enabled"]
    assert not config["safety"]["sleep_computer"]
    config["mode"] = "Browser"
    manager.save(config)
    assert manager.load().config == config
    assert not list(tmp_path.glob(".config_*"))


def test_corrupt_backup_and_repair(tmp_path):
    path = tmp_path / "config.json"
    old = b"{broken JSON"
    path.write_bytes(old)
    result = ConfigManager(path).load()
    assert result.restored and "domyślne" in result.message
    assert result.backup.read_bytes() == old
    assert json.loads(path.read_text())["schema_version"] == 1


def test_future_version_preserved(tmp_path):
    path = tmp_path / "config.json"
    config = defaults()
    config["schema_version"] = 99
    old = json.dumps(config)
    path.write_text(old)
    result = ConfigManager(path).load()
    assert result.restored
    assert path.read_text() == old
    assert result.backup.read_text() == old
    with pytest.raises(ConfigVersionError):
        validate_config(config)


def test_failed_replace_preserves_previous_settings(tmp_path):
    path = tmp_path / "config.json"
    manager = ConfigManager(path)
    manager.save(defaults())
    old = path.read_bytes()
    config = defaults()
    config["mode"] = "Media"
    with patch("src.gesture_assistant.core.config_manager.os.replace", side_effect=OSError("disk")):
        with pytest.raises(OSError):
            manager.save(config)
    assert path.read_bytes() == old
    assert not list(tmp_path.glob(".config_*"))


def test_backup_failure_does_not_overwrite(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b"broken")
    target = "src.gesture_assistant.core.config_manager.shutil.copy2"
    with patch(target, side_effect=OSError("disk")):
        with pytest.raises(OSError):
            ConfigManager(path).load()
    assert path.read_bytes() == b"broken"


def test_reset_preserves_old_and_duplicate_json_is_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"schema_version":1,"schema_version":2}')
    result = ConfigManager(path).load()
    assert result.restored and result.backup.exists()
    reset = ConfigManager(path).reset()
    assert reset.backup.exists()
    assert reset.config == defaults()


@pytest.mark.parametrize("mode", ["Auto", "Teams", "Browser", "Presentation", "Media", "System"])
def test_all_modes(mode):
    config = defaults()
    config["mode"] = mode
    assert validate_config(config)["mode"] == mode


def test_invalid_shortcut_and_application_in_config(tmp_path):
    config = defaults()
    config["targets"]["shortcuts"] = {"mute": "ctrl++m"}
    with pytest.raises(ValueError):
        validate_config(config)
    config = defaults()
    config["targets"]["applications"] = {"app": str(tmp_path / "missing.exe")}
    with pytest.raises(ValueError):
        validate_config(config)

