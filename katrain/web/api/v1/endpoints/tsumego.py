"""Tsumego API endpoints."""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from katrain.web.core.db import get_db
from katrain.web.core.models_db import TsumegoProblem, UserTsumegoProgress
from katrain.web.api.v1.endpoints.auth import get_current_user, get_current_user_optional
from katrain.web.models import User


router = APIRouter()


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
def get_levels(db: Session = Depends(get_db)):
    """Get all available difficulty levels with category counts."""
    rows = db.query(
        TsumegoProblem.level,
        TsumegoProblem.category,
        func.count(TsumegoProblem.id),
    ).group_by(TsumegoProblem.level, TsumegoProblem.category).all()

    # Aggregate into {level: {category: count}}
    levels: dict[str, dict[str, int]] = {}
    for level, category, count in rows:
        levels.setdefault(level, {})[category] = count

    result = []
    for level, categories in sorted(levels.items(), key=lambda x: level_sort_key(x[0])):
        result.append(LevelInfo(
            level=level,
            categories=categories,
            total=sum(categories.values()),
        ))
    return result


@router.get("/levels/{level}/categories", response_model=List[CategoryInfo])
def get_categories(level: str, db: Session = Depends(get_db)):
    """Get categories for a specific difficulty level."""
    level = level.lower()

    rows = db.query(
        TsumegoProblem.category,
        func.count(TsumegoProblem.id),
    ).filter(TsumegoProblem.level == level).group_by(TsumegoProblem.category).all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"Level {level} not found")

    category_names = {
        "life-death": "死活题",
        "tesuji": "手筋题",
        "endgame": "官子题",
    }

    return [
        CategoryInfo(
            category=cat,
            name=category_names.get(cat, cat),
            count=count,
        )
        for cat, count in rows
    ]


@router.get("/levels/{level}/categories/{category}", response_model=List[ProblemSummary])
def get_problems(
    level: str,
    category: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get problems for a level/category with pagination."""
    level = level.lower()

    problems = (
        db.query(TsumegoProblem)
        .filter(TsumegoProblem.level == level, TsumegoProblem.category == category)
        .order_by(TsumegoProblem.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    if not problems and offset == 0:
        # Check if level/category exist at all
        exists = db.query(TsumegoProblem.id).filter(
            TsumegoProblem.level == level, TsumegoProblem.category == category
        ).first()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Level {level} / category {category} not found")

    return [
        ProblemSummary(
            id=p.id,
            level=p.level,
            category=p.category,
            hint=p.hint,
            initialBlack=p.initial_black or [],
            initialWhite=p.initial_white or [],
        )
        for p in problems
    ]


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
