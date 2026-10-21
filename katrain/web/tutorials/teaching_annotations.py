"""Source-bound diagram teaching guides, separate from intersection marks."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from katrain.web.tutorials.workbench_models import Int, Point, StrictValue

Coordinate = Annotated[float, Field(strict=True, allow_inf_nan=False)]
DrawingPoint = Annotated[list[Coordinate], Field(min_length=2, max_length=2)]
ObjectId = Annotated[str, Field(min_length=1, max_length=100)]


class RegionDividers(StrictValue):
    columns: Annotated[list[Coordinate], Field(max_length=32)]
    rows: Annotated[list[Coordinate], Field(max_length=32)]


class TeachingArrow(StrictValue):
    model_config = ConfigDict(extra="forbid", serialize_by_alias=True)

    id: ObjectId
    from_: DrawingPoint = Field(alias="from")
    to: DrawingPoint


class TeachingCallout(StrictValue):
    id: ObjectId
    anchor: Point
    side: Literal["top", "right"]
    text: Annotated[str, Field(min_length=1, max_length=40)]


class TeachingAnnotations(StrictValue):
    schema_version: Int
    source_pointer: Annotated[str, Field(min_length=1, max_length=1000, pattern=r"^/")]
    image_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    region_dividers: RegionDividers | None = None
    arrows: list[TeachingArrow] = Field(default_factory=list, max_length=64)
    callouts: list[TeachingCallout] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def content(self):
        if self.schema_version != 1:
            raise ValueError("Teaching annotations require schema_version 1")
        if not (self.region_dividers or self.arrows or self.callouts):
            raise ValueError("Teaching annotations require a drawing object")
        ids = [item.id for item in [*self.arrows, *self.callouts]]
        if len(ids) != len(set(ids)):
            raise ValueError("Teaching object IDs must be unique")
        return self

    def validate_for_size(self, size):
        def inside(point):
            return all(0 <= value <= size - 1 for value in point)

        if self.region_dividers:
            divisions = [self.region_dividers.columns, self.region_dividers.rows]
            if not any(divisions):
                raise ValueError("Region dividers cannot be empty")
            for axis in divisions:
                if len(axis) != len(set(axis)) or any(not 0 < value < size - 1 for value in axis):
                    raise ValueError("Region divider must be unique and inside the board")
        for arrow in self.arrows:
            if not inside(arrow.from_) or not inside(arrow.to) or arrow.from_ == arrow.to:
                raise ValueError("Teaching arrow endpoints must differ and be inside the board")
        for callout in self.callouts:
            col, row = callout.anchor
            if not inside(callout.anchor) or not callout.text.strip():
                raise ValueError("Teaching callout requires an in-board anchor and text")
            if (callout.side == "top" and row != 0) or (callout.side == "right" and col != size - 1):
                raise ValueError("Teaching callout must anchor to its board edge")
