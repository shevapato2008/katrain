"""Configuration for katrain-cron service. All values from environment variables."""

import os


# Database
DATABASE_URL = os.getenv("KATRAIN_DATABASE_URL", "sqlite:///./db.sqlite3")
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
