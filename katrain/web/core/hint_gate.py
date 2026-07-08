"""Gating chain for the AI hint (选点白灯): scene → anti-cheat → billing → engine routing.

Q1 decision (2026-07-02): billing is a PROTOCOL STUB. The paid-analysis track
(feature/rk3588-ui phases 4b+) will implement a BillingHintGate over
core/billing.py reserve/commit/refund once the cloud billing proxy exists —
board-mode billing REST currently 503s all balance ops (endpoints/billing.py),
so local charging is impossible anyway. Until then DefaultHintGate routes purely
by static config: 'cloud' | 'local' | 'off'.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class HintDecision:
    allowed: bool
    engine: str = "local"  # "local" | "cloud"
    reason: str = ""  # machine-readable denial reason for the frontend toast
    charge_ref: Optional[str] = None  # billing reservation id (paid-analysis, later)


class HintGate(Protocol):
    def check(self, *, game_type: str, user_id: Optional[int]) -> HintDecision: ...

    def settle(self, charge_ref: Optional[str], success: bool) -> None: ...


class DefaultHintGate:
    """Config-only gate: no billing."""

    def __init__(self, hint_engine: str = "local"):
        self._engine = hint_engine

    def check(self, *, game_type: str, user_id: Optional[int] = None) -> HintDecision:
        if game_type != "free":
            return HintDecision(allowed=False, reason="ranked_forbidden")
        if self._engine == "off":
            return HintDecision(allowed=False, reason="disabled")
        return HintDecision(allowed=True, engine=self._engine)

    def settle(self, charge_ref: Optional[str], success: bool) -> None:
        return None
