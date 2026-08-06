"""Append-only public snapshots of the executable nine-profile engine catalog."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping

from .canonical import canonical_hash, float_hex

ACTIVE_CATALOG_VERSION = "pikafish-r1"


@dataclass(frozen=True)
class EngineProfile:
    level: int
    name: str
    anchor: int
    nodes: int | None
    movetime_ms: int | None
    multipv: int
    window_cp: int | None
    temp_cp: int | None
    p: float
    band_lo: int | None
    band_hi: int | None
    sharp_gain: float
    resignation_enabled: bool
    resignation_score_cp: int
    resignation_move_count: int
    profile_hash: str = ""


@dataclass(frozen=True)
class EngineCatalog:
    version: str
    profiles: tuple[EngineProfile, ...]

    def profile(self, level: int) -> EngineProfile:
        if level < 1 or level > len(self.profiles):
            raise KeyError(level)
        profile = self.profiles[level - 1]
        if profile.level != level:
            raise KeyError(level)
        return profile


def profile_public_config(profile: EngineProfile) -> dict[str, object]:
    return {
        "anchor": profile.anchor,
        "band_hi": profile.band_hi,
        "band_lo": profile.band_lo,
        "level": profile.level,
        "movetime_ms": profile.movetime_ms,
        "multipv": profile.multipv,
        "name": profile.name,
        "nodes": profile.nodes,
        "p_hex": float_hex(profile.p),
        "resignation_enabled": profile.resignation_enabled,
        "resignation_move_count": profile.resignation_move_count,
        "resignation_score_cp": profile.resignation_score_cp,
        "sharp_gain_hex": float_hex(profile.sharp_gain),
        "temp_cp": profile.temp_cp,
        "window_cp": profile.window_cp,
    }


def profile_hash(profile: EngineProfile) -> str:
    return canonical_hash(profile_public_config(profile))


def _profile(
    level: int,
    name: str,
    anchor: int,
    nodes: int | None,
    movetime_ms: int | None,
    multipv: int,
    window_cp: int | None,
    temp_cp: int | None,
    p: float,
    band_lo: int | None,
    band_hi: int | None,
    sharp_gain: float,
) -> EngineProfile:
    profile = EngineProfile(
        level=level,
        name=name,
        anchor=anchor,
        nodes=nodes,
        movetime_ms=movetime_ms,
        multipv=multipv,
        window_cp=window_cp,
        temp_cp=temp_cp,
        p=p,
        band_lo=band_lo,
        band_hi=band_hi,
        sharp_gain=sharp_gain,
        resignation_enabled=level >= 3,
        resignation_score_cp=500,
        resignation_move_count=3,
    )
    return replace(profile, profile_hash=profile_hash(profile))


_ACTIVE_PROFILES = (
    _profile(1, "新手", 1010, 10_000, None, 128, 180, 130, 0.30, 200, 700, 2.0),
    _profile(2, "入门", 1260, 10_000, None, 20, 165, 120, 0.27, 185, 630, 2.0),
    _profile(3, "初级", 1510, 16_000, None, 12, 130, 88, 0.20, 150, 500, 1.9),
    _profile(4, "中级", 1760, 24_000, None, 10, 105, 70, 0.155, 125, 410, 1.85),
    _profile(5, "高级", 1960, 40_000, None, 8, 85, 55, 0.115, 100, 330, 1.75),
    _profile(6, "精英", 2160, 60_000, None, 6, 66, 42, 0.085, 80, 260, 1.65),
    _profile(7, "大师", 2360, 100_000, None, 4, 50, 31, 0.06, 60, 200, 1.5),
    _profile(8, "特级", 2560, 120_000, None, 3, 23, 14, 0.028, 33, 115, 1.35),
    _profile(9, "满血", 2900, None, 1200, 1, None, None, 0.0, None, None, 1.0),
)

# r0 is the last shipped pre-RK3562 snapshot: level 8 used the historical
# 150k-node budget. It remains complete so old reservations/Outbox rows can be
# verified. Catalog versions are append-only; never mutate or delete snapshots.
_R0_PROFILES = tuple(
    _profile(
        profile.level,
        profile.name,
        profile.anchor,
        150_000 if profile.level == 8 else profile.nodes,
        profile.movetime_ms,
        profile.multipv,
        profile.window_cp,
        profile.temp_cp,
        profile.p,
        profile.band_lo,
        profile.band_hi,
        profile.sharp_gain,
    )
    for profile in _ACTIVE_PROFILES
)

SUPPORTED_CATALOGS: Mapping[str, EngineCatalog] = MappingProxyType(
    {
        "pikafish-r0": EngineCatalog("pikafish-r0", _R0_PROFILES),
        ACTIVE_CATALOG_VERSION: EngineCatalog(ACTIVE_CATALOG_VERSION, _ACTIVE_PROFILES),
    }
)


def active_catalog() -> EngineCatalog:
    return SUPPORTED_CATALOGS[ACTIVE_CATALOG_VERSION]
