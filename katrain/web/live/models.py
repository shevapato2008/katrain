"""Data models for the live broadcasting module."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MatchSource(str, Enum):
    """Data source for live matches."""
    XINGZHEN = "xingzhen"
    WEIQI_ORG = "weiqi_org"


class MatchStatus(str, Enum):
    """Status of a live match."""
    LIVE = "live"
    FINISHED = "finished"


class TopMove(BaseModel):
    """AI recommended move."""
    move: str  # e.g., "H3"
    visits: int
    winrate: float  # 0-1
    score_lead: float  # Black's lead in points
    prior: float  # Policy prior probability
    pv: list[str] = Field(default_factory=list)  # Principal variation
    psv: float = 0.0  # playSelectionValue - KataGo's composite ranking metric


class MoveAnalysis(BaseModel):
    """Analysis data for a single move."""
    match_id: str
    move_number: int
    move: Optional[str] = None  # The actual move played, e.g., "Q16"
    player: Optional[str] = None  # "B" or "W"
    winrate: float  # Black's winrate (0-1)
    score_lead: float  # Black's lead in points
    top_moves: list[TopMove] = Field(default_factory=list)
    ownership: Optional[list[list[float]]] = None  # 2D grid of ownership (-1 to 1, positive=Black)
    is_brilliant: bool = False  # 妙手
    is_mistake: bool = False  # 问题手
    is_questionable: bool = False  # 疑问手
    delta_score: float = 0.0  # Score change from previous move
    delta_winrate: float = 0.0  # Winrate change from previous move

    @classmethod
    def classify_move(cls, delta_score: float, brilliant_threshold: float = 2.0,
                     mistake_threshold: float = -3.0, questionable_threshold: float = -1.5) -> dict:
        """Classify a move based on score change thresholds.

        Returns dict with is_brilliant, is_mistake, is_questionable flags.
        Note: delta_score is from the perspective of the player who moved.
        """
        return {
            "is_brilliant": delta_score >= brilliant_threshold,
            "is_mistake": delta_score <= mistake_threshold,
            "is_questionable": mistake_threshold < delta_score <= questionable_threshold,
        }


class LiveMatch(BaseModel):
    """A live or recently finished match."""
    id: str  # Internal ID (format: {source}_{source_id})
    source: MatchSource
    source_id: str  # Original ID from the data source
    tournament: str  # Tournament/event name
    round_name: Optional[str] = None  # Round info (e.g., "Final", "Semi-final")
    date: datetime
    player_black: str
    player_white: str
    black_rank: Optional[str] = None  # e.g., "9p", "7d"
    white_rank: Optional[str] = None
    status: MatchStatus
    result: Optional[str] = None  # e.g., "B+R", "W+3.5"
    move_count: int = 0
    current_winrate: float = 0.5  # Black's winrate (from XingZhen)
    current_score: float = 0.0  # Black's score lead (from XingZhen)
    katago_winrate: Optional[float] = None  # Black's winrate (from local KataGo)
    katago_score: Optional[float] = None  # Black's score lead (from local KataGo)
    sgf: Optional[str] = None
    moves: list[str] = Field(default_factory=list)  # List of moves in coordinate format
    last_updated: datetime = Field(default_factory=datetime.now)
    # Game rules and komi
    board_size: int = 19  # Board size (9, 13, 19)
    komi: float = 7.5  # Komi (compensation points for white)
    rules: str = "chinese"  # Rules: "chinese", "japanese", "korean", etc.

    # Analysis data (populated by KataGo)
    analysis: dict[int, MoveAnalysis] = Field(default_factory=dict)  # move_number -> analysis

    @property
    def display_title(self) -> str:
        """Generate a display title for the match."""
        title = self.tournament
        if self.round_name:
            title += f" {self.round_name}"
        return title

    @property
    def players_display(self) -> str:
        """Generate player display string."""
        black = self.player_black
        white = self.player_white
        if self.black_rank:
            black += f" {self.black_rank}"
        if self.white_rank:
            white += f" {self.white_rank}"
        return f"{black} vs {white}"

    def to_summary(self) -> dict:
        """Convert to a summary dict for list display (without full moves/analysis)."""
        return {
            "id": self.id,
            "source": self.source.value,
            "tournament": self.tournament,
            "round_name": self.round_name,
            "date": self.date.isoformat(),
            "player_black": self.player_black,
            "player_white": self.player_white,
            "black_rank": self.black_rank,
            "white_rank": self.white_rank,
            "status": self.status.value,
            "result": self.result,
            "move_count": self.move_count,
            "current_winrate": self.current_winrate,
            "current_score": self.current_score,
            "last_updated": self.last_updated.isoformat(),
            "board_size": self.board_size,
            "komi": self.komi,
            "rules": self.rules,
        }


class UpcomingMatch(BaseModel):
    """An upcoming match in the schedule."""
    id: str
    tournament: str
    round_name: Optional[str] = None
    scheduled_time: datetime
    player_black: Optional[str] = None  # May be TBD
    player_white: Optional[str] = None
    source_url: Optional[str] = None  # Link to more info

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tournament": self.tournament,
            "round_name": self.round_name,
            "scheduled_time": self.scheduled_time.isoformat(),
            "player_black": self.player_black,
            "player_white": self.player_white,
            "source_url": self.source_url,
        }


class LiveConfig(BaseModel):
    """Configuration for the live module."""
    # Data source settings
    xingzhen_enabled: bool = True
    xingzhen_api_base: str = "https://api.19x19.com/api/engine/golives"
    # WeiqiOrg disabled: SGF data is encrypted/encoded, cannot parse moves
    # Will be re-enabled in Phase 2 once decryption is implemented
    weiqi_org_enabled: bool = False
    weiqi_org_api_base: str = "https://wqapi.cwql.org.cn"

    # Polling intervals (seconds)
    list_interval: int = 60  # How often to refresh match list
    moves_interval: int = 3  # How often to poll for new moves (live games)
    analysis_interval: int = 5  # How often to run analysis

    # Analysis settings
    analysis_max_visits: int = 500
    use_local_katago: bool = True

    # Display thresholds
    pv_moves: int = 10  # Number of PV moves to show
    pv_anim_time: float = 0.3  # Animation time per move
    brilliant_threshold: float = 2.0  # Score gain to mark as brilliant
    mistake_threshold: float = -3.0  # Score loss to mark as mistake
    questionable_threshold: float = -1.5  # Score loss for questionable
