import os
import uuid as uuid_module
from pydantic import BaseModel

# 仓库里跟着代码走的字面量默认值。**唯一真源**——生产装配（下方 env 装配处）与
# 字段默认值都引用它，不得各自再抄一份，否则改一处漏一处（参见 assert_secret_key_is_safe）。
INSECURE_DEFAULT_SECRET_KEY = "katrain-secret-key-change-this-in-production"

# HS256 用短密钥可以离线穷举——拿到任意一个 token 就能反推密钥并伪造管理员。
MIN_SECRET_KEY_CHARS = 32


def assert_secret_key_is_safe(mode: str, secret_key: str) -> None:
    """服务端模式下必须显式注入一个**足够长**的密钥。

    盒子（board）跑本地库、不对外签发身份，放行。

    为什么不只挡默认字面量：compose 的 `:?` 只保护 compose 这一条入口。
    直接 `python -m katrain`、systemd、或别的部署路径传进来的空串、空白、
    单字符都会通过，而 HS256 的短密钥可以离线穷举 —— 拿到任意一个 token
    就能反推密钥并伪造管理员。
    """
    if mode != "server":
        return
    if not secret_key or not secret_key.strip():
        raise RuntimeError("拒绝以空 SECRET_KEY 启动服务端：设置 KATRAIN_SECRET_KEY。")
    if len(secret_key.strip()) < MIN_SECRET_KEY_CHARS:
        raise RuntimeError(
            f"SECRET_KEY 太短（{len(secret_key.strip())} 字符，至少 {MIN_SECRET_KEY_CHARS}）："
            "HS256 短密钥可离线穷举。用 `python -c \"import secrets;print(secrets.token_urlsafe(48))\"` 生成。"
        )
    if secret_key == INSECURE_DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "拒绝以内置默认 SECRET_KEY 启动服务端：任何人都能用仓库里的字面量伪造任意用户的 token。"
            "请设置环境变量 KATRAIN_SECRET_KEY（建议 `python -c \"import secrets;print(secrets.token_urlsafe(48))\"`）。"
        )


class Settings(BaseModel):
    PROJECT_NAME: str = "KaTrain Web UI"
    VERSION: str = "1.17.1"
    API_V1_STR: str = "/api/v1"

    KATRAIN_HOST: str = "0.0.0.0"
    KATRAIN_PORT: int = 8001

    SESSION_TIMEOUT: int = 3600
    MAX_SESSIONS: int = 100

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
    SECRET_KEY: str = INSECURE_DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 90

    # 空库首次启动时创建管理员账号用的口令。**默认空 = 不创建任何账号**。
    # 从环境注入（KATRAIN_ADMIN_BOOTSTRAP_PASSWORD），用完即应清掉。
    ADMIN_BOOTSTRAP_PASSWORD: str = ""

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

        data.setdefault("SECRET_KEY", os.getenv("KATRAIN_SECRET_KEY", INSECURE_DEFAULT_SECRET_KEY))
        data.setdefault("ADMIN_BOOTSTRAP_PASSWORD", os.getenv("KATRAIN_ADMIN_BOOTSTRAP_PASSWORD", ""))
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
