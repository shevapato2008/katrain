"""API endpoints for personal game library (user_games) and analysis data."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from katrain.web.models import User
from katrain.web.api.v1.endpoints.auth import get_current_user

router = APIRouter()


# ── Request/Response Models ──

class UserGameCreate(BaseModel):
    sgf_content: str
    source: str  # play_ai / play_human / import / research
    title: Optional[str] = None
    player_black: Optional[str] = None
    player_white: Optional[str] = None
    result: Optional[str] = None
    board_size: int = 19
    rules: str = "chinese"
    komi: float = 7.5
    move_count: int = 0
    category: str = "game"  # game / position
    game_type: Optional[str] = None
    event: Optional[str] = None
    game_date: Optional[str] = None


class UserGameUpdate(BaseModel):
    title: Optional[str] = None
    sgf_content: Optional[str] = None
    player_black: Optional[str] = None
    player_white: Optional[str] = None
    result: Optional[str] = None
    move_count: Optional[int] = None
    updated_at: Optional[str] = None  # For optimistic locking


# ── Endpoints ──

@router.get("/")
async def list_user_games(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    category: Optional[str] = None,
    source: Optional[str] = None,
    sort: str = "created_at_desc",
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    repo = request.app.state.user_game_repo
    return repo.list(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        category=category,
        source=source,
        sort=sort,
        q=q,
    )


@router.post("/")
async def create_user_game(
    request: Request,
    game_in: UserGameCreate,
    current_user: User = Depends(get_current_user),
):
    repo = request.app.state.user_game_repo
    return repo.create(
        user_id=current_user.id,
        sgf_content=game_in.sgf_content,
        source=game_in.source,
        title=game_in.title,
        player_black=game_in.player_black,
        player_white=game_in.player_white,
        result=game_in.result,
        board_size=game_in.board_size,
        rules=game_in.rules,
        komi=game_in.komi,
        move_count=game_in.move_count,
        category=game_in.category,
        game_type=game_in.game_type,
        event=game_in.event,
        game_date=game_in.game_date,
    )


@router.get("/{game_id}")
async def get_user_game(
    request: Request,
    game_id: str,
    current_user: User = Depends(get_current_user),
):
    repo = request.app.state.user_game_repo
    game = repo.get(game_id, current_user.id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.put("/{game_id}")
async def update_user_game(
    request: Request,
    game_id: str,
    game_in: UserGameUpdate,
    current_user: User = Depends(get_current_user),
):
    repo = request.app.state.user_game_repo
    try:
        game = repo.update(
            game_id,
            current_user.id,
            updated_at=game_in.updated_at,
            title=game_in.title,
            sgf_content=game_in.sgf_content,
            player_black=game_in.player_black,
            player_white=game_in.player_white,
            result=game_in.result,
            move_count=game_in.move_count,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.delete("/{game_id}")
async def delete_user_game(
    request: Request,
    game_id: str,
    current_user: User = Depends(get_current_user),
):
    repo = request.app.state.user_game_repo
    deleted = repo.delete(game_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Game not found")
    return {"status": "deleted"}


# ── Analysis Data Endpoints ──

@router.get("/{game_id}/analysis")
async def get_analysis(
    request: Request,
    game_id: str,
    start_move: int = 0,
    limit: int = 400,
    current_user: User = Depends(get_current_user),
):
    # Verify ownership
    game_repo = request.app.state.user_game_repo
    game = game_repo.get(game_id, current_user.id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    analysis_repo = request.app.state.user_game_analysis_repo
    return analysis_repo.get_analysis(game_id, start_move=start_move, limit=limit)


@router.get("/{game_id}/analysis/{move_number}")
async def get_move_analysis(
    request: Request,
    game_id: str,
    move_number: int,
    current_user: User = Depends(get_current_user),
):
    # Verify ownership
    game_repo = request.app.state.user_game_repo
    game = game_repo.get(game_id, current_user.id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    analysis_repo = request.app.state.user_game_analysis_repo
    record = analysis_repo.get_move_analysis(game_id, move_number)
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found for this move")
    return record
