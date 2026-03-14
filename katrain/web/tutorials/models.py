from typing import Any, List, Literal, Optional
from pydantic import BaseModel


class Category(BaseModel):
    id: str
    slug: str
    title: str
    summary: str
    order: int
    topic_count: int
    cover_asset: Optional[str] = None


class Topic(BaseModel):
    id: str
    category_id: str
    slug: str
    title: str
    summary: str
    tags: Optional[List[str]] = None
    difficulty: Optional[str] = None
    estimated_minutes: Optional[int] = None


class Step(BaseModel):
    id: str
    example_id: str
    order: int
    narration: str
    image_asset: Optional[str] = None
    audio_asset: Optional[str] = None
    audio_duration_ms: Optional[int] = None
    board_mode: Literal["image", "sgf"]  # enforces rendering contract at API boundary
    board_payload: Optional[Any] = None


class Example(BaseModel):
    id: str
    topic_id: str
    title: str
    summary: str
    order: int
    total_duration_sec: Optional[float] = None
    step_count: int
    steps: List[Step]


class TutorialProgress(BaseModel):
    example_id: str
    topic_id: str
    last_step_id: Optional[str] = None
    completed: bool
    last_played_at: Optional[str] = None


class ProgressUpdate(BaseModel):
    topic_id: str
    last_step_id: str
    completed: bool
