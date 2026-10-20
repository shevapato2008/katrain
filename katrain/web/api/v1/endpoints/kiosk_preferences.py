"""Preferences shared by all Go kiosk sessions on this device."""

from pathlib import Path
from threading import Lock

from fastapi import APIRouter, HTTPException

from katrain.web.core.kiosk_preferences import TypographyPreference, TypographyPreferenceStore


router = APIRouter()
TYPOGRAPHY_PATH = Path("~/.katrain/kiosk-typography.json").expanduser()
_store: TypographyPreferenceStore | None = None
_store_init_lock = Lock()


def _preference_store() -> TypographyPreferenceStore:
    global _store
    with _store_init_lock:
        if _store is None or _store.path != TYPOGRAPHY_PATH:
            _store = TypographyPreferenceStore(TYPOGRAPHY_PATH)
    return _store


@router.get("/typography", response_model=TypographyPreference)
def get_typography() -> TypographyPreference:
    try:
        return _preference_store().read()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Typography preference unavailable") from exc


@router.put("/typography", response_model=TypographyPreference)
def set_typography(preference: TypographyPreference) -> TypographyPreference:
    try:
        return _preference_store().write(preference)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Typography preference could not be saved") from exc
