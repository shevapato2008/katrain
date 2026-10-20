"""Small, lossless v2 diagram components shared by calibration and imports."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Int = Annotated[int, Field(strict=True)]
Point = Annotated[list[Int], Field(min_length=2, max_length=2)]


class StrictValue(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnownRegion(StrictValue):
    col: Int
    row: Int
    cols: Annotated[int, Field(strict=True, gt=0)]
    rows: Annotated[int, Field(strict=True, gt=0)]


class SourceRegion(KnownRegion):
    confirmed: bool


class Viewport(StrictValue):
    col: Int
    row: Int
    size: Annotated[int, Field(strict=True, gt=0)] | None = None
    cols: Annotated[int, Field(strict=True, gt=0)] | None = None
    rows: Annotated[int, Field(strict=True, gt=0)] | None = None

    @model_validator(mode="after")
    def dimensions(self):
        if self.size is None and (self.cols is None or self.rows is None):
            raise ValueError("viewport requires size or both cols and rows")
        return self


class UnknownStone(StrictValue):
    point: Point
    color: None
    evidence: str | None = None


class ReplayMove(StrictValue):
    kind: Literal["move", "pass"]
    color: Literal["B", "W"] | None
    point: Point | None
    printed_number: str | None

    @model_validator(mode="after")
    def pass_point(self):
        if self.kind == "pass" and self.point is not None:
            raise ValueError("pass requires null point")
        return self


class ReplayInitial(StrictValue):
    stones: dict[str, list[Point]]
    unknown_stones: list[UnknownStone]
    labels: dict[str, str] | None = None
    letters: dict[str, str] | None = None
    shapes: dict[str, str] | None = None
    known_region: KnownRegion | None
    to_play: Literal["B", "W"] | None


class ReplayEvidence(StrictValue):
    kind: Literal["source", "linked_record"]
    source_pointer: str
    description: str
    reference_sha256: str | None = None


class Replay(StrictValue):
    status: Literal["complete", "needs_calibration"]
    initial: ReplayInitial | None
    moves: list[ReplayMove]
    evidence: ReplayEvidence | None = None
