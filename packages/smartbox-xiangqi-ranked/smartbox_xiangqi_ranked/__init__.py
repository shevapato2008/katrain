"""Public surface of the shared SmartBox Xiangqi ranked contract."""

from .canonical import canonical_event, canonical_hash, canonical_json, canonical_preview, float_hex, hash_event
from .catalog import ACTIVE_CATALOG_VERSION, SUPPORTED_CATALOGS, active_catalog, profile_hash
from .scoring import (
    SCORING_CONTRACT_VERSION,
    SUPPORTED_CONTRACTS,
    RatingChange,
    RatingState,
    apply_one,
    apply_one_v4,
    pick_level,
    project_three,
    tier_of,
)

__all__ = [
    "ACTIVE_CATALOG_VERSION",
    "SCORING_CONTRACT_VERSION",
    "SUPPORTED_CATALOGS",
    "SUPPORTED_CONTRACTS",
    "RatingChange",
    "RatingState",
    "active_catalog",
    "apply_one",
    "apply_one_v4",
    "canonical_event",
    "canonical_hash",
    "canonical_json",
    "canonical_preview",
    "float_hex",
    "hash_event",
    "pick_level",
    "profile_hash",
    "project_three",
    "tier_of",
]
