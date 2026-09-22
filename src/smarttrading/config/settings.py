from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Mode(StrEnum):
    BACKTEST = "backtest"
    PAPER = "paper"


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = "sqlite:///data/smarttrading.db"


class RiskSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_asset_allocation: float = Field(gt=0, le=1)
    max_portfolio_exposure: float = Field(gt=0, le=1)
    max_order_notional: Decimal = Field(gt=0)
    max_daily_loss: float = Field(gt=0, le=1)
    max_drawdown: float = Field(gt=0, le=1)
    stale_data_seconds: int = Field(gt=0)
    anomalous_price_deviation: float = Field(gt=0, le=1)


class ExecutionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    maker_fee_bps: float = Field(ge=0)
    taker_fee_bps: float = Field(ge=0)
    spread_bps: float = Field(ge=0)
    slippage_bps: float = Field(ge=0)
    simulated_latency_ms: int = Field(ge=0)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SMARTTRADING__",
        env_nested_delimiter="__",
        extra="forbid",
    )
    mode: Mode = Mode.PAPER
    assets: tuple[str, ...] = ("BTC/USDT", "ETH/USDT")
    timeframes: tuple[str, ...] = ("5m", "15m", "1h")
    base_currency: str = "USDT"
    initial_cash: Decimal = Field(gt=0)
    database: DatabaseSettings
    risk: RiskSettings
    execution: ExecutionSettings
    log_level: str = "INFO"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        del settings_cls
        # Operator environment must override the versioned YAML passed as init data.
        return env_settings, init_settings, dotenv_settings, file_secret_settings

    @field_validator("assets")
    @classmethod
    def unique_spot_assets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("assets must be non-empty and unique")
        if any(asset.count("/") != 1 for asset in value):
            raise ValueError("assets must use BASE/QUOTE notation")
        return value

    @field_validator("timeframes")
    @classmethod
    def supported_timeframes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        allowed = {"5m", "15m", "1h", "4h"}
        if not value or not set(value) <= allowed:
            raise ValueError(f"timeframes must be a subset of {sorted(allowed)}")
        return value


def load_settings(path: str | Path = "config/default.yaml") -> AppSettings:
    """Load versioned YAML, then apply SMARTTRADING__ nested environment overrides."""
    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a mapping")
    return AppSettings(**raw)
