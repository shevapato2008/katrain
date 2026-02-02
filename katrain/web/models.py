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
    credits: float = 10000.0
    avatar_url: Optional[str] = None
    created_at: Optional[Union[str, datetime]] = None

class UserInDB(User):
    hashed_password: str
