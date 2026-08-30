from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator


class Limits(BaseModel):
    max_order_value_rub: float = Field(gt=0)
    max_daily_buy_turnover_rub: float = Field(gt=0)
    max_daily_sell_turnover_rub: float = Field(gt=0)
    max_single_stock_exposure_pct: float = Field(gt=0, le=1)
    min_cash_reserve_rub: float = Field(ge=0)
    max_orders_per_run: int = Field(gt=0)


class ScheduleConfig(BaseModel):
    interval_minutes: int = Field(gt=0)
    trading_start: str
    trading_end: str
    timezone: str = "Europe/Moscow"


class IndicatorsConfig(BaseModel):
    candle_interval: Literal["hour", "day"] = "hour"
    lookback_days: int = Field(gt=0, default=60)


class AppConfig(BaseModel):
    mode: Literal["sandbox", "production"]
    trading_enabled: bool
    dry_run: bool
    production_ack: bool = False
    watchlist: list[str] = Field(min_length=1)
    limits: Limits
    schedule: ScheduleConfig
    indicators: IndicatorsConfig = IndicatorsConfig()

    # Заполняются load_config() из окружения, не хранятся в config.yaml.
    tinvest_token: str = Field(default="", exclude=True, repr=False)
    tinvest_account_id: str = Field(default="", exclude=True, repr=False)

    @model_validator(mode="after")
    def _check_production_requires_ack(self) -> "AppConfig":
        if self.mode == "production" and not self.production_ack:
            raise ValueError(
                "mode: production требует также production_ack: true в config.yaml "
                "— это осознанное подтверждение человека на торговлю реальными деньгами."
            )
        return self

    @property
    def should_execute_orders(self) -> bool:
        return self.trading_enabled and not self.dry_run

    @property
    def watchlist_set(self) -> set[str]:
        return set(self.watchlist)


def load_config(config_path: str | Path = "config/config.yaml", env_path: str | Path | None = None) -> AppConfig:
    config_path = Path(config_path)
    # override=True: .env обязан быть источником истины для конфига агента. Без этого
    # load_dotenv() молча пропускает переменные, которые уже есть в окружении процесса.
    load_dotenv(dotenv_path=env_path or Path(".env"), override=True)

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    cfg = AppConfig.model_validate(raw)

    suffix = "SANDBOX" if cfg.mode == "sandbox" else "PROD"
    token_env_var = f"TINVEST_TOKEN_{suffix}"
    account_env_var = f"TINVEST_ACCOUNT_ID_{suffix}"
    token = os.environ.get(token_env_var, "")
    account_id = os.environ.get(account_env_var, "")

    missing = [
        name
        for name, value in ((token_env_var, token), (account_env_var, account_id))
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Не заданы переменные окружения: "
            + ", ".join(missing)
            + ". Заполните .env (см. .env.example)."
        )

    return cfg.model_copy(update={"tinvest_token": token, "tinvest_account_id": account_id})
