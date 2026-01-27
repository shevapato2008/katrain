"""Tsumego API endpoints."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from katrain.web.core.db import get_db
from katrain.web.core.models_db import TsumegoProblem, UserTsumegoProgress
from katrain.web.api.v1.endpoints.auth import get_current_user, get_current_user_optional
from katrain.web.models import User


router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "life-n-death"
INDEX_FILE = DATA_DIR / "index.json"


# Response models
class LevelInfo(BaseModel):
    level: str
    categories: dict[str, int]  # category -> count
    total: int


class CategoryInfo(BaseModel):
    category: str
    name: str
    count: int


class ProblemSummary(BaseModel):
    id: str
    level: str
    category: str
    hint: str
    initialBlack: List[str]
    initialWhite: List[str]


class ProblemDetail(BaseModel):
    id: str
    level: str
    category: str
    hint: str
    boardSize: int
    initialBlack: List[str]
    initialWhite: List[str]
    sgfContent: str


class ProgressData(BaseModel):
    problemId: str
    completed: bool
    attempts: int
    firstCompletedAt: Optional[str] = None
    lastAttemptAt: Optional[str] = None
    lastDuration: Optional[int] = None


class ProgressUpdate(BaseModel):
    completed: bool
    attempts: int
    lastDuration: Optional[int] = None


def load_index() -> dict:
    """Load index.json file."""
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=500, detail="Index file not found. Run generate_tsumego_index.py")
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def level_sort_key(level: str) -> tuple:
    """Sort levels: 15K, 14K, ..., 1K, 1D, 2D, ..., 7D (weakest to strongest)."""
    level = level.upper()
    if level.endswith('K'):
        # Kyu levels: higher number = weaker = comes first
        return (0, -int(level[:-1]))
    elif level.endswith('D'):
        # Dan levels: lower number = weaker = comes first
        return (1, int(level[:-1]))
    return (2, 0)


@router.get("/levels", response_model=List[LevelInfo])
def get_levels():
    """Get all available difficulty levels with category counts."""
    index = load_index()
    result = []
    for level, data in sorted(index["levels"].items(), key=lambda x: level_sort_key(x[0])):
        categories = {cat: len(ids) for cat, ids in data["categories"].items()}
        result.append(LevelInfo(
            level=level,
            categories=categories,
            total=sum(categories.values())
        ))
    return result


@router.get("/levels/{level}/categories", response_model=List[CategoryInfo])
def get_categories(level: str):
    """Get categories for a specific difficulty level."""
    index = load_index()
    level = level.lower()  # Normalize to lowercase
    if level not in index["levels"]:
        raise HTTPException(status_code=404, detail=f"Level {level} not found")

    category_names = {
        "life-death": "死活题",
        "tesuji": "手筋题",
        "endgame": "官子题"
    }

    result = []
    for cat, ids in index["levels"][level]["categories"].items():
        result.append(CategoryInfo(
            category=cat,
            name=category_names.get(cat, cat),
            count=len(ids)
        ))
    return result


@router.get("/levels/{level}/categories/{category}", response_model=List[ProblemSummary])
def get_problems(
    level: str,
    category: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000)
):
    """Get problems for a level/category with pagination."""
    index = load_index()
    level = level.lower()  # Normalize to lowercase

    if level not in index["levels"]:
        raise HTTPException(status_code=404, detail=f"Level {level} not found")

    categories = index["levels"][level]["categories"]
    if category not in categories:
        raise HTTPException(status_code=404, detail=f"Category {category} not found")

    problem_ids = categories[category][offset:offset + limit]

    result = []
    for pid in problem_ids:
        p = index["problems"].get(pid)
        if p:
            result.append(ProblemSummary(
                id=p["id"],
                level=p["level"],
                category=p["category"],
                hint=p["hint"],
                initialBlack=p["initialBlack"],
                initialWhite=p["initialWhite"]
            ))
    return result


@router.get("/problems/{problem_id}", response_model=ProblemDetail)
def get_problem(problem_id: str, db: Session = Depends(get_db)):
    """Get full problem details including SGF content."""
    problem = db.query(TsumegoProblem).filter(TsumegoProblem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail=f"Problem {problem_id} not found")

    return ProblemDetail(
        id=problem.id,
        level=problem.level,
        category=problem.category,
        hint=problem.hint,
        boardSize=problem.board_size,
        initialBlack=problem.initial_black or [],
        initialWhite=problem.initial_white or [],
        sgfContent=problem.sgf_content or ""
    )


@router.get("/progress", response_model=dict[str, ProgressData])
async def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's progress on all problems."""
    progress_list = db.query(UserTsumegoProgress).filter(
        UserTsumegoProgress.user_id == current_user.id
    ).all()

    result = {}
    for p in progress_list:
        result[p.problem_id] = ProgressData(
            problemId=p.problem_id,
            completed=p.completed,
            attempts=p.attempts,
            firstCompletedAt=p.first_completed_at.isoformat() if p.first_completed_at else None,
            lastAttemptAt=p.last_attempt_at.isoformat() if p.last_attempt_at else None,
            lastDuration=p.last_duration
        )
    return result


@router.post("/progress/{problem_id}")
async def update_progress(
    problem_id: str,
    data: ProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's progress on a specific problem."""
    # Verify problem exists
    problem = db.query(TsumegoProblem).filter(TsumegoProblem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail=f"Problem {problem_id} not found")

    progress = db.query(UserTsumegoProgress).filter(
        UserTsumegoProgress.user_id == current_user.id,
        UserTsumegoProgress.problem_id == problem_id
    ).first()

    now = datetime.utcnow()

    if progress:
        progress.completed = data.completed
        progress.attempts = data.attempts
        progress.last_attempt_at = now
        if data.lastDuration is not None:
            progress.last_duration = data.lastDuration
        if data.completed and not progress.first_completed_at:
            progress.first_completed_at = now
    else:
        progress = UserTsumegoProgress(
            user_id=current_user.id,
            problem_id=problem_id,
            completed=data.completed,
            attempts=data.attempts,
            last_attempt_at=now,
            last_duration=data.lastDuration,
            first_completed_at=now if data.completed else None
        )
        db.add(progress)

    db.commit()
    return {"success": True}
