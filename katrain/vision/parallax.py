"""Stone-parallax correction parameters and calibration fit -- pure math, no I/O.

Derivation and measured inputs: superpowers/tracks/vision-stone-parallax/geometry.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParallaxParams:
    """What BoardStateExtractor needs: the camera nadir in the geometry-lock warp's continuous grid
    coordinates (fx = column, fy = row) and the contraction factor k = (H - h) / H."""

    nadir_fx: float
    nadir_fy: float
    k: float

    @property
    def nadir(self) -> tuple[float, float]:
        return (self.nadir_fx, self.nadir_fy)

    def to_dict(self) -> dict:
        return {"nadir_fx": self.nadir_fx, "nadir_fy": self.nadir_fy, "k": self.k}
