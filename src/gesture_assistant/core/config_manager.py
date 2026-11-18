import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.gesture_assistant.config.schema import ConfigVersionError, validate_config

MAX_CONFIG_BYTES = 1024 * 1024


def reject_constant(value):
    raise ValueError(f"Niedozwolona stała JSON: {value}")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Powtórzone pole JSON: {key}")
        result[key] = value
    return result


def project_config_path(explicit=None):
    if explicit is not None:
        return Path(explicit)
    root = Path(__file__).resolve().parents[3]
    if (root / "main.py").is_file():
        return root / "config.json"
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".config"
    return base / "GestureAssistant" / "config.json"


def defaults():
    path = Path(__file__).resolve().parents[1] / "config" / "default_config.json"
    return validate_config(json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class ConfigLoadResult:
    config: dict
    restored: bool
    message: str
    backup: Path | None = None


class ConfigManager:
    def __init__(self, path: Path):
        self.path = Path(path)

    def save(self, config):
        config = validate_config(config)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".config_", dir=self.path.parent)
        temporary = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
                json.dump(config, target, ensure_ascii=False, indent=2, allow_nan=False)
                target.write("\n")
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self):
        if not self.path.exists():
            config = defaults()
            return ConfigLoadResult(
                config,
                False,
                "Brak pliku; użyto bezpiecznych ustawień domyślnych.",
            )
        try:
            if self.path.stat().st_size > MAX_CONFIG_BYTES:
                raise ValueError("Plik konfiguracji przekracza 1 MiB.")
            config = json.loads(
                self.path.read_text(encoding="utf-8"),
                parse_constant=reject_constant,
                object_pairs_hook=unique_object,
            )
            return ConfigLoadResult(validate_config(config), False, "Wczytano ustawienia.")
        except ConfigVersionError as exc:
            backup = self._backup()
            return ConfigLoadResult(defaults(), True, str(exc), backup)
        except (ValueError, UnicodeError) as exc:

            backup = self._backup()
            config = defaults()
            self.save(config)
            return ConfigLoadResult(
                config,
                True,
                f"Przywrócono ustawienia domyślne: {exc}",
                backup,
            )

    def _backup(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = self.path.with_name(self.path.name + f".invalid_{stamp}.bak")
        shutil.copy2(self.path, backup)
        return backup

    def reset(self):
        backup = self._backup() if self.path.exists() else None
        config = defaults()
        self.save(config)
        return ConfigLoadResult(config, True, "Przywrócono ustawienia domyślne.", backup)

