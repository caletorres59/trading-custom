from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml


@dataclass(frozen=True)
class RiskLimits:
    max_daily_loss_pct: Decimal
    max_trade_risk_pct: Decimal
    max_position_pct: Decimal
    max_portfolio_exposure_pct: Decimal
    max_drawdown_pct: Decimal
    max_leverage: Decimal
    max_trades_per_day: int


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    params: dict


@dataclass(frozen=True)
class AppConfig:
    mode: str
    symbols: list[str]
    timeframe: str
    strategy: StrategyConfig
    risk: RiskLimits
    loop_interval_seconds: int
    starting_equity: Decimal
    database_url: str
    binance_api_key: str | None
    binance_api_secret: str | None


def load_config(path: str | Path = "config/config.yaml") -> AppConfig:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    risk_raw = raw["risk"]
    risk = RiskLimits(
        max_daily_loss_pct=Decimal(str(risk_raw["max_daily_loss_pct"])),
        max_trade_risk_pct=Decimal(str(risk_raw["max_trade_risk_pct"])),
        max_position_pct=Decimal(str(risk_raw["max_position_pct"])),
        max_portfolio_exposure_pct=Decimal(str(risk_raw["max_portfolio_exposure_pct"])),
        max_drawdown_pct=Decimal(str(risk_raw["max_drawdown_pct"])),
        max_leverage=Decimal(str(risk_raw["max_leverage"])),
        max_trades_per_day=int(risk_raw["max_trades_per_day"]),
    )

    strategy_raw = raw["strategy"]
    strategy = StrategyConfig(
        name=strategy_raw["name"],
        params={k: v for k, v in strategy_raw.items() if k != "name"},
    )

    return AppConfig(
        mode=raw.get("mode", "PAPER"),
        symbols=raw["symbols"],
        timeframe=raw["timeframe"],
        strategy=strategy,
        risk=risk,
        loop_interval_seconds=int(raw.get("loop_interval_seconds", 60)),
        starting_equity=Decimal(str(raw.get("starting_equity", "1000"))),
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./aurora.db"),
        binance_api_key=os.environ.get("BINANCE_TESTNET_API_KEY") or None,
        binance_api_secret=os.environ.get("BINANCE_TESTNET_API_SECRET") or None,
    )
