"""KaTrain Live Broadcasting Module

This module provides live game broadcasting functionality.

In the cron-based architecture:
- katrain-cron handles polling, analysis, and translations
- This module reads from the shared PostgreSQL database
- LiveService maintains in-memory caches for fast API responses
"""

from katrain.web.live.models import LiveMatch, MoveAnalysis, UpcomingMatch, LiveConfig
from katrain.web.live.service import LiveService, create_live_service
from katrain.web.live.cache import LiveCache
from katrain.web.live.analysis_repo import (
    LiveAnalysisRepo,
    PRIORITY_LIVE_NEW,
    PRIORITY_USER_VIEW,
    PRIORITY_LIVE_BACKFILL,
    PRIORITY_FINISHED,
)

__all__ = [
    "LiveMatch",
    "MoveAnalysis",
    "UpcomingMatch",
    "LiveConfig",
    "LiveService",
    "create_live_service",
    "LiveCache",
    "LiveAnalysisRepo",
    "PRIORITY_LIVE_NEW",
    "PRIORITY_USER_VIEW",
    "PRIORITY_LIVE_BACKFILL",
    "PRIORITY_FINISHED",
]
