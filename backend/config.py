from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str
    resend_api_key: str
    email_notifications: str
    ted_api_key: Optional[str] = None
    anac_base_url: str = "https://api.anticorruzione.it/apicig/v1.0"
    cbs_lat: float = 45.6952
    cbs_lng: float = 8.9969
    default_radius_km: float = 50.0
    scheduler_hour: int = 6
    scheduler_minute: int = 0
    dashboard_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
