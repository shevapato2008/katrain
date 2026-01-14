import os
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "KaTrain Web UI"
    VERSION: str = "1.17.1"
    API_V1_STR: str = "/api/v1"
    
    KATRAIN_HOST: str = os.getenv("KATRAIN_HOST", "0.0.0.0")
    KATRAIN_PORT: int = int(os.getenv("KATRAIN_PORT", 8001))
    
    SESSION_TIMEOUT: int = int(os.getenv("KATRAIN_SESSION_TIMEOUT", 3600))
    MAX_SESSIONS: int = int(os.getenv("KATRAIN_MAX_SESSIONS", 100))
    
    # Engine Settings
    LOCAL_KATAGO_URL: str = os.getenv("LOCAL_KATAGO_URL", "http://127.0.0.1:8000")
    CLOUD_KATAGO_URL: str = os.getenv("CLOUD_KATAGO_URL", "")

settings = Settings()
