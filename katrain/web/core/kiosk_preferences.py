"""Small device-scoped preferences persisted on the kiosk data volume."""

import json
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TypographyPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    font: Literal["wenkai", "kaiti", "lishu", "heiti"] = "wenkai"
    size: Literal["large", "medium", "small"] = "large"


class TypographyPreferenceStore:
    """Serialize reads/writes and replace one versioned JSON file atomically."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = Lock()

    def read(self) -> TypographyPreference:
        with self._lock:
            if not self.path.exists():
                return TypographyPreference()
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1:
                raise ValueError("unsupported kiosk typography preference version")
            return TypographyPreference.model_validate(data["typography"])

    def write(self, preference: TypographyPreference) -> TypographyPreference:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            staged_path = None
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as staged:
                    staged_path = Path(staged.name)
                    json.dump({"version": 1, "typography": preference.model_dump()}, staged, ensure_ascii=False)
                    staged.write("\n")
                    staged.flush()
                    os.fsync(staged.fileno())
                os.replace(staged_path, self.path)
            finally:
                if staged_path is not None:
                    staged_path.unlink(missing_ok=True)
            return preference


class DeviceAppearance(BaseModel):
    language: Literal["zh", "zh-TW", "en", "ja", "ko"] = "zh"
    font: Literal["wenkai", "kai", "daoli", "hei"] = "wenkai"


def read_device_appearance() -> DeviceAppearance:
    """Read the wizard authority without treating an existing broken file as first boot."""
    path = Path(os.environ.get("SMARTBOX_SETTINGS_PATH", "/var/lib/smartbox/settings.json"))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DeviceAppearance()
    if not isinstance(data, dict):
        raise ValueError("settings root must be an object")
    language = data.get("language")
    font = data.get("font")
    return DeviceAppearance(
        language=language if language in ("zh", "zh-TW", "en", "ja", "ko") else "zh",
        font=font if font in ("wenkai", "kai", "daoli", "hei") else "wenkai",
    )
