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
ANALYSIS_WINDOW_SIZE_REPORTING = int(os.getenv("CRON_ANALYSIS_WINDOW_SIZE_REPORTING", "4"))
ANALYSIS_REQUEST_TIMEOUT = float(os.getenv("CRON_ANALYSIS_REQUEST_TIMEOUT", "60.0"))
ANALYSIS_MAX_VISITS = int(os.getenv("CRON_ANALYSIS_MAX_VISITS", "500"))
ANALYSIS_PREEMPT_THRESHOLD = int(os.getenv("CRON_ANALYSIS_PREEMPT_THRESHOLD", "500"))

# 人类倾向（KataGo human SL 模型）。空字符串 = 关掉这个特性，报告里就不会有这一列。
#
# 引擎侧前置条件：分析服务必须是带 -human-model 启动的（生产/测试两台 2026-08-31 实测
# 都满足，/health 的 has_human_model 为 true）。**只设 profile 而引擎没加载人类模型时，
# KataGo 会让整条 query 失败**，不是静默降级 —— 所以这个开关要能一键关掉。
#
# 合法取值只有 KataGo 内置的那 29 档（rank_20k..rank_1k, rank_1d..rank_9d）加 preaz_* /
# proyear_*；写错（比如 rank_10d 这种不存在的档）同样是整条 query 报错。
#
# **默认关闭（2026-09-01）**。Fan 裁定这一列先不上：「规则不统一，没有很好的产品价值」。
# 依据是当日在测试引擎上对同一个局面（report 16 第 98 手）逐档实测出来的：
#
#     rank_5k       H9=86.3%  J14=4.9%
#     rank_1d       H9=51.3%  J14=31.9%
#     rank_5d       J14=56.7%  H9=27.4%     ← 到这一档答案翻了个个儿
#     rank_9d       J14=60.0%  H9=28.3%
#     proyear_2023  J14=57.5%  H9=30.8%
#
# 也就是说**这个数完全由 profile 决定**，而 profile 是这里写死的一个常量 —— 对职业棋谱
# 和对新手都不贴切，屏幕上那个百分比没法自证该信谁。要复活这个特性，先解决参照系：
# 跟棋局档次走，或跟看报告的人自己的段位走（后者要在生成报告时定档，一份报告只能烤一档）。
#
# 开着它的代价不只是多一列：`rootNumSymmetriesToSample=8` 是为了让 humanPrior 在两台机器
# 上稳定才加的（见下），每一手都要多做 8 次根节点对称采样。字段没人读的时候这是纯浪费。
HUMAN_SL_PROFILE = os.getenv("CRON_HUMAN_SL_PROFILE", "")

# 人类网前向的对称采样数。**这不是可选的调优项，删掉它会让同一手棋在两个页面上显示成
# 不同的数字。** 2026-08-31 在测试机与生产机上实测（同一局面、同一 profile rank_5d）：
#
#   不设       测试 0.1897 vs 生产 0.1709  → 差 1.9pp，屏上是「19人」对「17人」
#   设 8       测试 0.21017 vs 生产 0.21054 → 差 0.04pp，两边都是「21人」
#              同机重复三次：测试完全相同，生产只差 1e-8
#
# 而同进程内因为有 NN cache 永远一致 —— 也就是说不设它，本地开发和单测永远不会红，
# 只有用户屏幕上「报告里存的值」和「研究页现算的值」会打架。
# 代价是人类网前向 ×8（相对 500 visits 的搜索可忽略）。已实测该键可以逐条 override。
HUMAN_SL_SYMMETRIES = int(os.getenv("CRON_HUMAN_SL_SYMMETRIES", "8"))

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

# Report analysis (migrated from katrain-web)
REPORT_ANALYZE_ENABLED = os.getenv("CRON_REPORT_ANALYZE_ENABLED", "true").lower() == "true"
REPORT_CONCURRENCY = int(os.getenv("CRON_REPORT_CONCURRENCY", "3"))
REPORT_POLL_INTERVAL = float(os.getenv("CRON_REPORT_POLL_INTERVAL", "2.0"))
REPORT_ANALYSIS_PRIORITY = int(os.getenv("CRON_REPORT_ANALYSIS_PRIORITY", "1000"))

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

# Tutorial backup settings
TUTORIAL_BACKUP_ENABLED = os.getenv("CRON_TUTORIAL_BACKUP_ENABLED", "true").lower() == "true"
TUTORIAL_BACKUP_INTERVAL = int(os.getenv("CRON_TUTORIAL_BACKUP_INTERVAL", "86400"))  # 24 hours
TUTORIAL_BACKUP_RETENTION_DAYS = int(os.getenv("CRON_TUTORIAL_BACKUP_RETENTION_DAYS", "14"))
TUTORIAL_BACKUP_DIR = os.getenv("CRON_TUTORIAL_BACKUP_DIR", "data/tutorial_backups")

# LLM (Qwen via DashScope)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
LLM_MODEL = os.getenv("CRON_LLM_MODEL", "qwen-plus")
LLM_CONCURRENCY = int(os.getenv("CRON_LLM_CONCURRENCY", "3"))

# Logging
LOG_LEVEL = os.getenv("CRON_LOG_LEVEL", "INFO")
