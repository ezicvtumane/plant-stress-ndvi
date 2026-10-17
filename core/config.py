import os
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    try:
        from pydantic import BaseSettings
        SettingsConfigDict = None
    except ImportError:
        from pydantic.v1 import BaseSettings
        SettingsConfigDict = None

class Settings(BaseSettings):
    # Relay Config
    RELAY_PIN_NIR: int = 7  # PL7
    RELAY_PIN_RED: int = 4  # PL4
    RELAY_ACTIVE_LOW: bool = True
    
    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    STATIC_DIR: str = os.path.join(BASE_DIR, "static")
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    CSV_LOG: str = os.path.join(DATA_DIR, "measurements.csv")

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    else:
        class Config:
            env_file = ".env"
            extra = "ignore"

settings = Settings()
os.makedirs(settings.STATIC_DIR, exist_ok=True)
os.makedirs(settings.DATA_DIR, exist_ok=True)
