"""Configuration for katrain-cron service. All values from environment variables."""

import os


def _resolve_database_url() -> str:
    """Resolve DATABASE_URL: env var > ~/.katrain/config.json > SQLite fallback.

    Uses the same resolution logic as the web process to ensure both
    processes connect to the same database.
    """
    env_url = os.getenv("KATRAIN_DATABASE_URL")
    if env_url:
        return env_url

    # Try to load from config.json (same logic as katrain/web/core/config.py)
    import json
    from pathlib import Path

    for path in [Path.home() / ".katrain" / "config.json", Path("katrain/config.json")]:
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "server" in data and "database_url" in data["server"]:
                    return data["server"]["database_url"]
        except Exception:
            pass

    return "sqlite:///./db.sqlite3"


# Database
DATABASE_URL = _resolve_database_url()
DATABASE_POOL_SIZE = int(os.getenv("CRON_DB_POOL_SIZE", "20"))
DATABASE_MAX_OVERFLOW = int(os.getenv("CRON_DB_MAX_OVERFLOW", "10"))

# KataGo analysis endpoint (batch analysis instance)
KATAGO_URL = os.getenv("KATAGO_URL", "http://127.0.0.1:8002")
KATAGO_ANALYZE_PATH = os.getenv("KATAGO_ANALYZE_PATH", "/analyze")
KATAGO_HEALTH_PATH = os.getenv("KATAGO_HEALTH_PATH", "/health")

# Analysis flight window
ANALYSIS_WINDOW_SIZE = int(os.getenv("CRON_ANALYSIS_WINDOW_SIZE", "16"))
ANALYSIS_REQUEST_TIMEOUT = float(os.getenv("CRON_ANALYSIS_REQUEST_TIMEOUT", "60.0"))
ANALYSIS_MAX_VISITS = int(os.getenv("CRON_ANALYSIS_MAX_VISITS", "500"))
ANALYSIS_PREEMPT_THRESHOLD = int(os.getenv("CRON_ANALYSIS_PREEMPT_THRESHOLD", "500"))

# XingZhen API
XINGZHEN_BASE_URL = os.getenv("XINGZHEN_BASE_URL", "https://api.19x19.com/api/engine/golives")
XINGZHEN_ENABLED = os.getenv("CRON_XINGZHEN_ENABLED", "true").lower() == "true"

# YikeWeiQi API (弈客围棋)
YIKE_BASE_URL = os.getenv("YIKE_BASE_URL", "https://api-new.yikeweiqi.com")
YIKE_APP_KEY = os.getenv("YIKE_APP_KEY", "3396jtzhK57XhJom")
YIKE_APP_SECRET = os.getenv("YIKE_APP_SECRET", "hfdSXRKm0DQyLmNXmNCNkZpjy2o5q1Hk")
YIKE_ENABLED = os.getenv("CRON_YIKE_ENABLED", "true").lower() == "true"

# Pandanet-IGS (日本头衔战)
PANDANET_HOST = os.getenv("PANDANET_HOST", "igs.joyjoy.net")
PANDANET_PORT = int(os.getenv("PANDANET_PORT", "7777"))
PANDANET_ENABLED = os.getenv("CRON_PANDANET_ENABLED", "true").lower() == "true"
PANDANET_POLL_INTERVAL = int(os.getenv("CRON_PANDANET_POLL_INTERVAL", "300"))

# Job intervals (seconds)
FETCH_LIST_INTERVAL = int(os.getenv("CRON_FETCH_LIST_INTERVAL", "60"))
POLL_MOVES_INTERVAL = int(os.getenv("CRON_POLL_MOVES_INTERVAL", "3"))
TRANSLATE_INTERVAL = int(os.getenv("CRON_TRANSLATE_INTERVAL", "120"))
FETCH_UPCOMING_INTERVAL = int(os.getenv("CRON_FETCH_UPCOMING_INTERVAL", "7200"))  # 2 hours
CLEANUP_INTERVAL = int(os.getenv("CRON_CLEANUP_INTERVAL", "86400"))  # 24 hours

# Job enable/disable toggles
FETCH_LIST_ENABLED = os.getenv("CRON_FETCH_LIST_ENABLED", "true").lower() == "true"
POLL_MOVES_ENABLED = os.getenv("CRON_POLL_MOVES_ENABLED", "true").lower() == "true"
TRANSLATE_ENABLED = os.getenv("CRON_TRANSLATE_ENABLED", "true").lower() == "true"
ANALYZE_ENABLED = os.getenv("CRON_ANALYZE_ENABLED", "true").lower() == "true"
FETCH_UPCOMING_ENABLED = os.getenv("CRON_FETCH_UPCOMING_ENABLED", "true").lower() == "true"
CLEANUP_ENABLED = os.getenv("CRON_CLEANUP_ENABLED", "true").lower() == "true"

# Cleanup settings
CLEANUP_MATCH_RETENTION_DAYS = int(os.getenv("CRON_CLEANUP_MATCH_RETENTION_DAYS", "30"))
CLEANUP_ANALYSIS_RETENTION_DAYS = int(os.getenv("CRON_CLEANUP_ANALYSIS_RETENTION_DAYS", "30"))

# LLM (Qwen via DashScope)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
LLM_MODEL = os.getenv("CRON_LLM_MODEL", "qwen-plus")
LLM_CONCURRENCY = int(os.getenv("CRON_LLM_CONCURRENCY", "3"))

# Logging
LOG_LEVEL = os.getenv("CRON_LOG_LEVEL", "INFO")
