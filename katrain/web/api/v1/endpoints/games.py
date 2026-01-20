from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from datetime import datetime
from katrain.web.models import User
from katrain.web.api.v1.endpoints.auth import get_current_user

router = APIRouter()

class GameCreate(BaseModel):
    sgf_content: str
    result: str
    game_type: str = "free"
    black_id: int | None = None
    white_id: int | None = None

class GameResultUpdate(BaseModel):
    result: str
    winner_id: int | None = None

class GameResponse(BaseModel):
    id: int
    black_player_id: int | None = None
    white_player_id: int | None = None
    result: str | None = None
    game_type: str
    started_at: datetime
    sgf_content: str | None = None

@router.get("/", response_model=List[GameResponse])
async def list_my_games(
    request: Request,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
) -> Any:
    repo = request.app.state.game_repo
    games = repo.list_games(current_user.id, limit=limit, offset=skip)
    return games

@router.post("/", response_model=GameResponse)
async def create_game(
    request: Request,
    game_in: GameCreate,
    current_user: User = Depends(get_current_user)
) -> Any:
    repo = request.app.state.game_repo
    game = repo.create_game(
        user_id=current_user.id,
        sgf_content=game_in.sgf_content,
        result=game_in.result,
        game_type=game_in.game_type,
        black_id=game_in.black_id,
        white_id=game_in.white_id
    )
    return game

@router.post("/{game_id}/result", response_model=GameResponse)
async def record_game_result(
    request: Request,
    game_id: int,
    result_in: GameResultUpdate,
    current_user: User = Depends(get_current_user)
) -> Any:
    repo = request.app.state.game_repo
    try:
        game = repo.update_game_result(
            game_id=game_id,
            result=result_in.result,
            winner_id=result_in.winner_id
        )
        return game
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{game_id}", response_model=GameResponse)
async def read_game(
    request: Request,
    game_id: int,
    current_user: User = Depends(get_current_user)
) -> Any:
    repo = request.app.state.game_repo
    game = repo.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    # Authorization check? For now, allow reading any game if logged in.
    return game
