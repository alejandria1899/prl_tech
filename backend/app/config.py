from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PRL-Tech API"
    database_url: str = "postgresql+psycopg://prl_user:prl_password@localhost:5432/prl_tech"
    thingspeak_channel_id: str | None = None
    thingspeak_read_api_key: str | None = None
    thingspeak_default_results: int = 1000
    thingspeak_sync_enabled: bool = True
    thingspeak_sync_device_code: str = "home_dht22"
    thingspeak_sync_interval_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
