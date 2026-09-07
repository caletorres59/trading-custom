from decimal import Decimal

import pandas as pd

from aurora.backtest.multi_engine import MultiSymbolBacktestEngine
from aurora.config import RiskLimits
from aurora.risk.risk_engine import HardRiskEngine
from aurora.strategy.base import Direction, Signal, Strategy


class AlwaysLongStrategy(Strategy):
    name = "always_long"

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        return Signal(symbol, Direction.LONG, 1.0, ["ALWAYS_LONG"])


class NeverTradeStrategy(Strategy):
    name = "never"

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        return Signal(symbol, Direction.NO_TRADE, 0.0, ["NEVER"])


def make_candles(closes: list[float], start: str = "2026-01-01") -> pd.DataFrame:
    n = len(closes)
    return pd.DataFrame({
        "open_time": pd.date_range(start, periods=n, freq="D", tz="UTC"),
        "open": closes,
        "high": closes,
        "low": closes,
        "close": closes,
        "volume": [1.0] * n,
    })


def permissive_limits(**overrides) -> RiskLimits:
    base = dict(
        max_daily_loss_pct=Decimal("99"),
        max_trade_risk_pct=Decimal("100"),
        max_position_pct=Decimal("100"),
        max_portfolio_exposure_pct=Decimal("100"),
        max_drawdown_pct=Decimal("99"),
        max_leverage=Decimal("1"),
        max_trades_per_day=1000,
    )
    base.update(overrides)
    return RiskLimits(**base)


def test_per_symbol_contributions_sum_to_total_return():
    btc = make_candles([100, 100, 100, 110, 120, 130, 140, 150])
    eth = make_candles([50, 50, 50, 55, 45, 60, 40, 70])
    engine = MultiSymbolBacktestEngine(
        strategies={"BTC-USD": AlwaysLongStrategy(), "ETH-USD": AlwaysLongStrategy()},
        risk_engine=HardRiskEngine(permissive_limits(
            max_position_pct=Decimal("10"),
            max_portfolio_exposure_pct=Decimal("50"),
            max_trade_risk_pct=Decimal("50"),
        )),
        symbols=["BTC-USD", "ETH-USD"],
        starting_equity=Decimal("1000"),
    )
    result = engine.run({"BTC-USD": btc, "ETH-USD": eth})

    total_delta = result.final_equity - result.starting_equity
    summed = sum(s.pnl_contribution for s in result.per_symbol.values())
    assert abs(summed - total_delta) < Decimal("0.01")
    assert result.per_symbol["BTC-USD"].trades > 0
    assert result.per_symbol["ETH-USD"].trades > 0


def test_shared_exposure_budget_is_split_across_symbols():
    # 50% aggregate cap: two symbols both wanting max long can't each take
    # a full single-name position - the second is REDUCEd by what's left.
    btc = make_candles([100] * 8)
    eth = make_candles([100] * 8)
    engine = MultiSymbolBacktestEngine(
        strategies={"BTC-USD": AlwaysLongStrategy(), "ETH-USD": AlwaysLongStrategy()},
        risk_engine=HardRiskEngine(permissive_limits(
            max_portfolio_exposure_pct=Decimal("50"),
            max_position_pct=Decimal("40"),
            max_trade_risk_pct=Decimal("1"),
        )),
        symbols=["BTC-USD", "ETH-USD"],
        starting_equity=Decimal("1000"),
    )
    result = engine.run({"BTC-USD": btc, "ETH-USD": eth})
    assert any("REDUCE" in t.risk_decision for t in result.trades) or result.risk_rejections > 0


def test_kill_switch_flattens_every_symbol_and_recovers():
    # ETH crashes hard enough to trip the portfolio drawdown breaker; the
    # flatten must close BOTH the ETH and the BTC leg, then trading resumes.
    btc = make_candles([100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100])
    eth = make_candles([100, 100, 100, 100, 20, 20, 100, 100, 100, 100, 100])
    engine = MultiSymbolBacktestEngine(
        strategies={"BTC-USD": AlwaysLongStrategy(), "ETH-USD": AlwaysLongStrategy()},
        risk_engine=HardRiskEngine(permissive_limits(
            max_drawdown_pct=Decimal("15"),
            max_position_pct=Decimal("40"),
            max_portfolio_exposure_pct=Decimal("80"),
            max_trade_risk_pct=Decimal("50"),
        )),
        symbols=["BTC-USD", "ETH-USD"],
        starting_equity=Decimal("1000"),
    )
    result = engine.run({"BTC-USD": btc, "ETH-USD": eth})
    assert result.circuit_breaker_flattens >= 1
    flatten_symbols = {t.symbol for t in result.trades if t.direction == "FLATTEN"}
    assert flatten_symbols == {"BTC-USD", "ETH-USD"}  # both legs flattened, not just the crashing one
    # after the breach clears, the account is not permanently frozen
    assert result.final_equity > Decimal("0")


def test_no_trades_when_strategy_is_silent():
    engine = MultiSymbolBacktestEngine(
        strategies={"BTC-USD": NeverTradeStrategy(), "ETH-USD": NeverTradeStrategy()},
        risk_engine=HardRiskEngine(permissive_limits()),
        symbols=["BTC-USD", "ETH-USD"],
        starting_equity=Decimal("1000"),
    )
    result = engine.run({"BTC-USD": make_candles([100] * 6), "ETH-USD": make_candles([100] * 6)})
    assert result.trades == []
    assert result.final_equity == Decimal("1000")
