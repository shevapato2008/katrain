"""Pydantic response models for the tutorial module V2.

Hierarchy: Category → Book → Chapter → Section → Figure
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class TutorialCategoryOut(BaseModel):
    slug: str
    title: str
    summary: str
    order: int
    book_count: int = 0


class TutorialBookOut(BaseModel):
    id: int
    category: str
    subcategory: str
    title: str
    author: Optional[str] = None
    translator: Optional[str] = None
    slug: str
    chapter_count: int = 0

    class Config:
        from_attributes = True


class TutorialChapterOut(BaseModel):
    id: int
    book_id: int
    chapter_number: str
    title: str
    order: int
    section_count: int = 0

    class Config:
        from_attributes = True


class TutorialSectionOut(BaseModel):
    id: int
    chapter_id: int
    section_number: str
    title: str
    order: int
    figure_count: int = 0

    class Config:
        from_attributes = True


class TutorialFigureOut(BaseModel):
    id: int
    section_id: int
    page: int
    figure_label: str
    book_text: Optional[str] = None
    page_context_text: Optional[str] = None
    bbox: Optional[Dict[str, float]] = None
    page_image_path: Optional[str] = None
    board_payload: Optional[Any] = None
    narration: Optional[str] = None
    audio_asset: Optional[str] = None
    order: int

    class Config:
        from_attributes = True


class TutorialSectionDetailOut(TutorialSectionOut):
    """Section with all its figures included."""
    figures: List[TutorialFigureOut] = []


class TutorialBookDetailOut(TutorialBookOut):
    """Book with chapters and their sections."""
    chapters: List[TutorialChapterOut] = []


class StrictBoardPayload(BaseModel):
    """Validated board_payload — rejects malformed or oversized data."""
    size: int = 19
    stones: Dict[str, List[List[int]]]  # {"B": [[col,row]], "W": [[col,row]]}
    labels: Optional[Dict[str, str]] = None
    letters: Optional[Dict[str, str]] = None
    shapes: Optional[Dict[str, str]] = None
    highlights: Optional[List[List[int]]] = None
    # viewport is computed server-side, not accepted from client


class BoardPayloadUpdate(BaseModel):
    """Request body for updating a figure's board_payload."""
    board_payload: StrictBoardPayload
    expected_updated_at: Optional[str] = None  # ISO timestamp for optimistic locking
