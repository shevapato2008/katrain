from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field


class MoveRequest(BaseModel):
    session_id: str
    coords: Optional[List[int]] = Field(default=None, min_length=2, max_length=2)
    pass_move: bool = False


class UndoRedoRequest(BaseModel):
    session_id: str
    n_times: Union[int, str] = 1


class NavRequest(BaseModel):
    session_id: str
    node_id: Optional[int] = None


class PlayerSetupInfo(BaseModel):
    name: str
    player_type: str
    player_subtype: str


class NewGameRequest(BaseModel):
    session_id: str
    size: Optional[Union[int, str]] = 19
    handicap: Optional[int] = 0
    komi: Optional[float] = 6.5
    rules: Optional[str] = "japanese"
    clear_cache: bool = False
    players: Optional[Dict[str, PlayerSetupInfo]] = None
    # Per-game strength-ladder rung (1..41), injected non-persisted for this game
    # only. None = no rung this game (an ai:ladder player then fails closed). Range
    # validated server-side (see new_game handler) -> 422 on out-of-range values.
    ladder_rung: Optional[int] = None


class LadderStartGameRequest(BaseModel):
    """Start a 升降级对弈 game. Deliberately carries NO rung, NO game_type, and no
    board setup.

    The opponent tier comes from the player's own ladder state and the scoring
    game type is issued by the server, so neither can be chosen by a client that
    would like an easier opponent or a game that counts when it should not. Board
    size, ruleset and komi are fixed by the ladder for the same reason -- they are
    the conditions the rungs were measured under (ladder_repo.LADDER_BOARD_SIZE
    and friends). What is left is what is genuinely the player's: which seat, and
    how long they get to think.
    """

    session_id: str
    color: str = "B"
    #: Units are in the names on purpose. `timer/main_time` is stored in MINUTES
    #: (every consumer multiplies it by 60 -- katrain/web/interface.py:820), and a
    #: caller that read this field as seconds handed out 10-hour games.
    main_time_minutes: int = 10
    byo_length_seconds: int = 30
    byo_periods: int = 3


class EditGameRequest(BaseModel):
    session_id: str
    size: Optional[Union[int, str]] = None
    handicap: Optional[int] = None
    komi: Optional[float] = None
    rules: Optional[str] = None
    players: Optional[Dict[str, PlayerSetupInfo]] = None


class GameSettingsRequest(BaseModel):
    session_id: str
    mode: str  # newgame, setupposition, editgame
    settings: Dict[str, Any]


class LoadSGFRequest(BaseModel):
    session_id: str
    sgf: str
    skip_analysis: bool = False


class AnalysisScanRequest(BaseModel):
    session_id: str
    visits: Optional[int] = 50


class ConfigUpdateRequest(BaseModel):
    session_id: str
    setting: str
    value: Any


class ConfigBulkUpdateRequest(BaseModel):
    session_id: str
    updates: Dict[str, Any]


class UpdatePlayerRequest(BaseModel):
    session_id: str
    bw: str
    player_type: Optional[str] = None
    player_subtype: Optional[str] = None
    name: Optional[str] = None


class ToggleAnalysisRequest(BaseModel):
    session_id: str


class PVRequest(BaseModel):
    session_id: str
    pv: str


class ModeRequest(BaseModel):
    session_id: str
    mode: str


class InsertModeRequest(BaseModel):
    session_id: str
    mode: str = "toggle"


class UIToggleRequest(BaseModel):
    session_id: str
    setting: str


class LanguageRequest(BaseModel):
    session_id: str
    lang: str


class ThemeRequest(BaseModel):
    session_id: str
    theme: str


class AnalyzeExtraRequest(BaseModel):
    session_id: str
    mode: str
    kwargs: Optional[dict] = None


class FindMistakeRequest(BaseModel):
    session_id: str
    fn: str = "redo"


class SwitchBranchRequest(BaseModel):
    session_id: str
    direction: int


class TsumegoRequest(BaseModel):
    session_id: str
    ko: bool = False
    margin: Optional[int] = None


class SelfPlayRequest(BaseModel):
    session_id: str
    until_move: Any
    target_b_advantage: Optional[float] = None


class SelectBoxRequest(BaseModel):
    session_id: str
    coords: List[int]


class GameAnalysisRequest(BaseModel):
    session_id: str
    visits: Optional[int] = None
    mistakes_only: bool = False
    move_range: Optional[List[int]] = None


class GameReportRequest(BaseModel):
    session_id: str
    depth_filter: Optional[List[float]] = None


class AnalyzeRequest(BaseModel):
    session_id: str
    payload: Dict[str, Any]


class RankEstimationRequest(BaseModel):
    strategy: str
    settings: Dict[str, Any]


class User(BaseModel):
    id: Optional[int] = None
    uuid: Optional[str] = None  # Unique UUID assigned at registration, used for KataGo requests
    username: str
    rank: str = "20k"
    net_wins: int = 0
    elo_points: int = 0
    credits: int = 10000
    is_admin: bool = False
    avatar_url: Optional[str] = None
    created_at: Optional[Union[str, datetime]] = None


class UserInDB(User):
    hashed_password: str


class CountRequest(BaseModel):
    session_id: str


class CountResponse(BaseModel):
    session_id: str
    accept: bool
