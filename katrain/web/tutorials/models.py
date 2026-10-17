"""Pydantic response models for the tutorial module V2.

Hierarchy: Category → Book → Chapter → Section → Figure
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from katrain.web.tutorials.media_profiles import public_video_fields
from katrain.web.tutorials.workbench_models import Int, Point, Replay, SourceRegion, UnknownStone, Viewport


class TutorialCategoryOut(BaseModel):
    slug: str
    title: str
    summary: str
    order: int
    book_count: int = 0


class TutorialBookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    subcategory: str
    title: str
    author: Optional[str] = None
    translator: Optional[str] = None
    slug: str
    chapter_count: int = 0


class TutorialChapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    chapter_number: str
    title: str
    order: int
    section_count: int = 0


class TutorialSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    section_number: str
    title: str
    order: int
    figure_count: int = 0
    has_video: bool = False


class TutorialFigureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section_id: int
    page: int
    figure_label: str
    book_text: Optional[str] = None
    page_context_text: Optional[str] = None
    bbox: Optional[Dict[str, float]] = None
    page_image_path: Optional[str] = None
    board_payload: Optional[Any] = None
    recognition_debug: Optional[Any] = None
    narration: Optional[str] = None
    audio_asset: Optional[str] = None
    video_asset: Optional[str] = None
    video_duration_ms: Optional[int] = None
    video_size_bytes: Optional[int] = None
    video_profiles: Dict[str, Optional[Dict[str, Any]]] = {}
    video_output_profile: Literal["galaxy-4k-v1", "legacy"] | None = None
    order: int
    updated_at: Optional[datetime] = None

    @model_validator(mode="after")
    def populate_video_profiles(self):
        fields = public_video_fields(self)
        self.video_profiles = fields["video_profiles"]
        self.video_output_profile = fields["video_output_profile"]
        return self

    @field_validator("updated_at")
    @classmethod
    def utc_version(cls, value: Optional[datetime]) -> Optional[datetime]:
        # SQLite strips timezone metadata; tutorial versions are always UTC.
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class TutorialFigureAdminOut(TutorialFigureOut):
    """Authenticated authoring response; reviewer identities stay out of public schemas."""

    board_review: Optional[Dict[str, Any]] = None
    video_2d_review: Optional[Dict[str, Any]] = None
    video_3d_review: Optional[Dict[str, Any]] = None
    review_validity: Optional[Dict[str, Any]] = None


class TutorialSectionDetailOut(TutorialSectionOut):
    """Section with all its figures included."""

    figures: List[TutorialFigureOut] = []


class TutorialBookDetailOut(TutorialBookOut):
    """Book with chapters and their sections."""

    chapters: List[TutorialChapterOut] = []


VALID_BOARD_SIZES = {9, 13, 19}


class StrictBoardPayload(BaseModel):
    """Validated board_payload — rejects malformed or oversized data."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Int | None = None
    unknown_stones: list[UnknownStone | Point] | None = None
    source_region: SourceRegion | None = None
    replay: Replay | None = None
    viewport: Viewport | None = None
    size: Int = 19
    stones: Dict[str, List[Point]]  # {"B": [[col,row]], "W": [[col,row]]}
    labels: Optional[Dict[str, str]] = None
    letters: Optional[Dict[str, str]] = None
    shapes: Optional[Dict[str, str]] = None
    highlights: Optional[List[List[int]]] = None
    # Legacy viewports are computed; explicit v2 viewports round-trip unchanged.

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: int) -> int:
        if v not in VALID_BOARD_SIZES:
            raise ValueError(f"size must be one of {sorted(VALID_BOARD_SIZES)}, got {v}")
        return v

    @model_validator(mode="after")
    def validate_coordinates(self) -> "StrictBoardPayload":
        max_coord = self.size - 1
        # Validate stones keys
        invalid_keys = set(self.stones.keys()) - {"B", "W"}
        if invalid_keys:
            raise ValueError(f"stones keys must be 'B' or 'W', got {invalid_keys}")
        # Validate stone coordinates
        for color, coords in self.stones.items():
            for pair in coords:
                if len(pair) != 2 or not (0 <= pair[0] <= max_coord and 0 <= pair[1] <= max_coord):
                    raise ValueError(f"stone coordinate {pair} out of bounds for size {self.size}")
        # Validate coordinate-keyed dicts (labels, letters, shapes)
        for field_name in ("labels", "letters", "shapes"):
            mapping = getattr(self, field_name)
            if not mapping:
                continue
            for key in mapping:
                parts = key.split(",")
                if len(parts) != 2:
                    raise ValueError(f"{field_name} key '{key}' must be 'col,row' format")
                col, row = int(parts[0]), int(parts[1])
                if not (0 <= col <= max_coord and 0 <= row <= max_coord):
                    raise ValueError(f"{field_name} coordinate '{key}' out of bounds for size {self.size}")
        # Validate highlights
        if self.highlights:
            for pair in self.highlights:
                if len(pair) != 2 or not (0 <= pair[0] <= max_coord and 0 <= pair[1] <= max_coord):
                    raise ValueError(f"highlight coordinate {pair} out of bounds for size {self.size}")
        if self.schema_version not in (None, 2):
            raise ValueError("schema_version must be 2 when supplied")

        def validate_setup(stones, unknowns, scope):
            seen = set()
            if set(stones) - {"B", "W"}:
                raise ValueError(f"{scope}: invalid stone color")
            for coords in stones.values():
                for point in coords:
                    if len(point) != 2 or not all(0 <= coordinate < self.size for coordinate in point):
                        raise ValueError(f"{scope}: point outside board")
                    if tuple(point) in seen:
                        raise ValueError(f"{scope}: duplicate occupied point")
                    seen.add(tuple(point))
            for stone in unknowns or []:
                point = stone.point if isinstance(stone, UnknownStone) else stone
                if not all(0 <= coordinate < self.size for coordinate in point) or tuple(point) in seen:
                    raise ValueError(f"{scope}: unknown stone overlaps or is outside board")
                seen.add(tuple(point))

        if self.schema_version == 2:
            if "size" not in self.model_fields_set:
                raise ValueError("v2 size must be explicit")
            if self.unknown_stones is None or any(not isinstance(stone, UnknownStone) for stone in self.unknown_stones):
                raise ValueError("v2 unknown_stones must explicitly list point/color evidence objects")
            if set(self.stones) != {"B", "W"}:
                raise ValueError("v2 stones must explicitly declare B and W")
        validate_setup(self.stones, self.unknown_stones, "Static diagram")

        def validate_region(region):
            if region is None:
                return
            cols = getattr(region, "cols", None) or getattr(region, "size", None)
            rows = getattr(region, "rows", None) or getattr(region, "size", None)
            if region.col < 0 or region.row < 0 or region.col + cols > self.size or region.row + rows > self.size:
                raise ValueError("Region is outside board")

        validate_region(self.source_region)
        validate_region(self.viewport)
        if self.replay:
            if self.schema_version != 2:
                raise ValueError("Replay requires schema_version 2")
            initial = self.replay.initial
            if initial:
                if set(initial.stones) != {"B", "W"}:
                    raise ValueError("Initial state stones must explicitly declare B and W")
                validate_setup(initial.stones, initial.unknown_stones, "Initial state")
                validate_region(initial.known_region)
                for field in ("labels", "letters", "shapes"):
                    for key in getattr(initial, field) or {}:
                        try:
                            col, row = map(int, key.split(","))
                        except (ValueError, TypeError) as exc:
                            raise ValueError("Initial marks require col,row coordinates") from exc
                        if not 0 <= col < self.size or not 0 <= row < self.size:
                            raise ValueError("Initial mark outside board")
            for move in self.replay.moves:
                if move.point is not None and not all(0 <= coordinate < self.size for coordinate in move.point):
                    raise ValueError("Replay point outside board")
            if self.replay.status == "complete":
                from katrain.web.tutorials.replay import validate_replay

                proof = validate_replay(self.model_dump(exclude_unset=True))
                if proof["status"] != "complete":
                    raise ValueError("; ".join(proof["issues"]))
        return self


class BoardPayloadUpdate(BaseModel):
    """Request body for updating a figure's board_payload."""

    board_payload: StrictBoardPayload
    expected_updated_at: Optional[str] = None  # ISO timestamp for optimistic locking


class NarrationUpdate(BaseModel):
    """Request body for updating a figure's narration text and audio asset."""

    narration: str
    audio_asset: Optional[str] = None
    video_asset: Optional[str] = None
    video_duration_ms: Optional[int] = None
    video_size_bytes: Optional[int] = None


class NarrationUpdateRequest(BaseModel):
    narration: str
