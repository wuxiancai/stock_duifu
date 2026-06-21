from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="A股短线量化辅助决策系统", alias="APP_NAME")
    app_env: Literal["development", "test", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    database_url: str = Field(
        default="postgresql+psycopg://stock:stock@127.0.0.1:5432/stock",
        alias="DATABASE_URL",
    )
    tushare_token: str = Field(default="", alias="TUSHARE_TOKEN")
    simulation_commission_rate: float = Field(default=0.0003, alias="SIMULATION_COMMISSION_RATE")
    simulation_stamp_tax_rate: float = Field(default=0.0005, alias="SIMULATION_STAMP_TAX_RATE")
    simulation_transfer_fee_rate: float = Field(default=0.00001, alias="SIMULATION_TRANSFER_FEE_RATE")
    simulation_min_commission: float = Field(default=5.0, alias="SIMULATION_MIN_COMMISSION")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_configured(self) -> bool:
        return self.database_url.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    return Settings()
