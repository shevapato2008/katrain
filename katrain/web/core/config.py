import os
import uuid as uuid_module
from pydantic import BaseModel


class Settings(BaseModel):
    PROJECT_NAME: str = "KaTrain Web UI"
    VERSION: str = "1.17.1"
    API_V1_STR: str = "/api/v1"

    KATRAIN_HOST: str = "0.0.0.0"
    KATRAIN_PORT: int = 8001

    SESSION_TIMEOUT: int = 3600
    MAX_SESSIONS: int = 100
    PREVIEW_MODE: bool = False

    # Engine Settings
    LOCAL_KATAGO_URL: str = "http://127.0.0.1:8000"
    CLOUD_KATAGO_URL: str = ""

    # Persistence
    DATABASE_PATH: str = "db.sqlite3"
    DATABASE_URL: str = "sqlite:///./db.sqlite3"

    # Media storage (tutorial video/audio/page images). See
    # superpowers/tracks/tutorial-database/plan.md.
    STORAGE_BACKEND: str = "local"          # local | s3
    S3_ENDPOINT_URL: str = ""               # MinIO: http://minio:9000 ; OSS: https://oss-cn-<region>.aliyuncs.com
    S3_REGION: str = ""                     # OSS: cn-hangzhou ...; MinIO can be blank
    S3_BUCKET: str = "tutorial-assets"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_PUBLIC_BASE_URL: str = ""            # client-reachable prefix: phase1 nginx domain; phase2 CDN domain
    S3_USE_PRESIGNED: bool = False          # private bucket -> public_url() returns a signed URL
    S3_PRESIGN_TTL_SEC: int = 3600

    # Security
    SECRET_KEY: str = "katrain-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 90

    DEFAULT_LANG: str = "cn"

    # Board mode settings (see design.md Section 4.2)
    KATRAIN_MODE: str = "server"  # "server" or "board"
    REMOTE_API_URL: str = ""  # Remote server URL for board mode, e.g. "https://katrain.example.com"
    DEVICE_ID: str = ""  # Unique device identifier, auto-generated if empty
    KATRAIN_BOX_SSO: bool = False
    KATRAIN_BOX_SSO_BRIDGE_KEY_PATH: str = "/etc/smartbox/box-sso-bridge.key"

    # Billing / paid-analysis (single-pool integer credits). Prices are per analysis action.
    BILLING_PRICES: dict = {"territory": 10, "hints": 10, "variations": 10}
    BILLING_PACKAGES: list = [
        {"package_id": "p6", "credits": 600, "amount_fen": 600, "title": "6 元 600 积分"},
        {"package_id": "p30", "credits": 3300, "amount_fen": 3000, "title": "30 元 3300 积分"},
        {"package_id": "p98", "credits": 12000, "amount_fen": 9800, "title": "98 元 12000 积分"},
    ]
    BILLING_FREE_GRANT: int = 10000  # initial credits for a new account
    BILLING_RESERVATION_TTL_SEC: int = 120  # stale 'reserved' refund threshold
    REDEEM_RATE_LIMIT: int = 5  # max failed redeem attempts / user / minute

    def __init__(self, **data):
        # Override with env vars if not provided in data
        data.setdefault("KATRAIN_HOST", os.getenv("KATRAIN_HOST", "0.0.0.0"))
        data.setdefault("KATRAIN_PORT", int(os.getenv("KATRAIN_PORT", 8001)))
        data.setdefault("SESSION_TIMEOUT", int(os.getenv("KATRAIN_SESSION_TIMEOUT", 3600)))
        data.setdefault("MAX_SESSIONS", int(os.getenv("KATRAIN_MAX_SESSIONS", 100)))
        data.setdefault("PREVIEW_MODE", os.getenv("KATRAIN_PREVIEW_MODE", "false").lower() in ("1", "true", "yes"))
        data.setdefault("LOCAL_KATAGO_URL", os.getenv("LOCAL_KATAGO_URL", "http://127.0.0.1:8000"))
        data.setdefault("CLOUD_KATAGO_URL", os.getenv("CLOUD_KATAGO_URL", ""))
        data.setdefault("DATABASE_PATH", os.getenv("KATRAIN_DATABASE_PATH", "db.sqlite3"))

        # New DATABASE_URL support
        env_db_url = os.getenv("KATRAIN_DATABASE_URL")
        if env_db_url:
            data["DATABASE_URL"] = env_db_url
        else:
            # Try to load from config.json
            import json
            from pathlib import Path

            try:
                # Check standard locations: ~/.katrain/config.json or ./katrain/config.json
                config_paths = [Path.home() / ".katrain" / "config.json", Path("katrain/config.json")]
                json_db_url = None
                for path in config_paths:
                    if path.exists():
                        with open(path, "r", encoding="utf-8") as f:
                            config_data = json.load(f)
                            # Check for "server": {"database_url": "..."}
                            if "server" in config_data and "database_url" in config_data["server"]:
                                json_db_url = config_data["server"]["database_url"]
                                break

                if json_db_url:
                    data["DATABASE_URL"] = json_db_url
                else:
                    # Fallback to sqlite using the DATABASE_PATH
                    data.setdefault("DATABASE_URL", f"sqlite:///./{data.get('DATABASE_PATH', 'db.sqlite3')}")
            except Exception as e:
                print(f"Warning: Failed to read config.json: {e}")
                # Fallback to sqlite using the DATABASE_PATH
                data.setdefault("DATABASE_URL", f"sqlite:///./{data.get('DATABASE_PATH', 'db.sqlite3')}")

        # Media storage settings
        data.setdefault("STORAGE_BACKEND", os.getenv("KATRAIN_STORAGE_BACKEND", "local"))
        data.setdefault("S3_ENDPOINT_URL", os.getenv("KATRAIN_S3_ENDPOINT_URL", ""))
        data.setdefault("S3_REGION", os.getenv("KATRAIN_S3_REGION", ""))
        data.setdefault("S3_BUCKET", os.getenv("KATRAIN_S3_BUCKET", "tutorial-assets"))
        data.setdefault("S3_ACCESS_KEY", os.getenv("KATRAIN_S3_ACCESS_KEY", ""))
        data.setdefault("S3_SECRET_KEY", os.getenv("KATRAIN_S3_SECRET_KEY", ""))
        data.setdefault("S3_PUBLIC_BASE_URL", os.getenv("KATRAIN_S3_PUBLIC_BASE_URL", ""))
        data.setdefault("S3_USE_PRESIGNED", os.getenv("KATRAIN_S3_USE_PRESIGNED", "false").lower() in ("1", "true", "yes"))

        data.setdefault("SECRET_KEY", os.getenv("KATRAIN_SECRET_KEY", "katrain-secret-key-change-this-in-production"))
        data.setdefault("DEFAULT_LANG", os.getenv("KATRAIN_DEFAULT_LANG", "cn"))

        # Board mode settings
        data.setdefault("KATRAIN_MODE", os.getenv("KATRAIN_MODE", "server"))
        data.setdefault("REMOTE_API_URL", os.getenv("KATRAIN_REMOTE_URL", ""))
        data.setdefault(
            "KATRAIN_BOX_SSO",
            os.getenv("KATRAIN_BOX_SSO", "0").lower() in ("1", "true", "yes"),
        )
        data.setdefault(
            "KATRAIN_BOX_SSO_BRIDGE_KEY_PATH",
            os.getenv(
                "KATRAIN_BOX_SSO_BRIDGE_KEY_PATH",
                "/etc/smartbox/box-sso-bridge.key",
            ),
        )
        device_id = os.getenv("KATRAIN_DEVICE_ID", "")
        if not device_id:
            device_id = uuid_module.uuid4().hex
        data.setdefault("DEVICE_ID", device_id)
        data.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", int(os.getenv("KATRAIN_REFRESH_TOKEN_EXPIRE_DAYS", 90)))

        # Board mode always uses local SQLite — ignore any PostgreSQL URL from config.json
        if data.get("KATRAIN_MODE") == "board" and not os.getenv("KATRAIN_DATABASE_URL"):
            db_path = data.get("DATABASE_PATH", "db.sqlite3")
            data["DATABASE_URL"] = f"sqlite:///./{db_path}"

        super().__init__(**data)


settings = Settings()
