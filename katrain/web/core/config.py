import os
from pydantic import BaseModel

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
    
    # Security
    SECRET_KEY: str = "katrain-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    DEFAULT_LANG: str = "cn"

    def __init__(self, **data):
        # Override with env vars if not provided in data
        data.setdefault("KATRAIN_HOST", os.getenv("KATRAIN_HOST", "0.0.0.0"))
        data.setdefault("KATRAIN_PORT", int(os.getenv("KATRAIN_PORT", 8001)))
        data.setdefault("SESSION_TIMEOUT", int(os.getenv("KATRAIN_SESSION_TIMEOUT", 3600)))
        data.setdefault("MAX_SESSIONS", int(os.getenv("KATRAIN_MAX_SESSIONS", 100)))
        data.setdefault("LOCAL_KATAGO_URL", os.getenv("LOCAL_KATAGO_URL", "http://127.0.0.1:8000"))
        data.setdefault("CLOUD_KATAGO_URL", os.getenv("CLOUD_KATAGO_URL", ""))
        data.setdefault("DATABASE_PATH", os.getenv("KATRAIN_DATABASE_PATH", "db.sqlite3"))
        data.setdefault("SECRET_KEY", os.getenv("KATRAIN_SECRET_KEY", "katrain-secret-key-change-this-in-production"))
        data.setdefault("DEFAULT_LANG", os.getenv("KATRAIN_DEFAULT_LANG", "cn"))
        super().__init__(**data)

settings = Settings()
