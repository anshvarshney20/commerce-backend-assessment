from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://commerce:commerce@localhost:5432/commerce"
    app_name: str = "commerce-backend"
    campaign_duration_minutes: int = 15
    campaign_target_orders: int = 10
    campaign_pool_amount: Decimal = Decimal("2000")
    platform_fee_pct: Decimal = Decimal("7")
    logistics_fee: Decimal = Decimal("80")


@lru_cache
def get_settings() -> Settings:
    return Settings()
