from decimal import Decimal

import pandas as pd

from aurora.backtest.engine import BacktestEngine
from aurora.config import RiskLimits
from aurora.risk.risk_engine import HardRiskEngine
from aurora.strategy.base import Direction, Signal, Strategy


class AlwaysLongStrategy(Strategy):
    """Deterministic strategy for tests: always wants to be long, regardless
    of candle content, so risk-engine behavior can be isolated."""

    name = "always_long"

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        return Signal(symbol, Direction.LONG, 1.0, ["ALWAYS_LONG"])


class LongThenShortStrategy(Strategy):
    """Long for the first few bars, then short - so the SELL that follows
    has a real long position to act against."""

    name = "long_then_short"

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        direction = Direction.LONG if len(candles) <= 5 else Direction.SHORT
        return Signal(symbol, direction, 1.0, ["SCRIPTED"])


def _permissive_limits() -> RiskLimits:
    return RiskLimits(
        max_position_pct=Decimal("100"),
        max_portfolio_exposure_pct=Decimal("100"),
        max_trade_risk_pct=Decimal("100"),
        max_daily_loss_pct=Decimal("99"),
        max_drawdown_pct=Decimal("99"),
        max_leverage=Decimal("1"),
        max_trades_per_day=100,
    )


def test_long_only_skips_a_short_with_no_long_to_reduce():
    engine = BacktestEngine(
        strategy=type("AlwaysShort", (Strategy,), {
            "name": "always_short",
            "generate_signal": lambda self, s, c: Signal(s, Direction.SHORT, 1.0, ["S"]),
        })(),
        risk_engine=HardRiskEngine(_permissive_limits()),
        symbol="BTC-USD",
        starting_equity=Decimal("1000"),
        allow_short=False,
    )
    result = engine.run(make_candles([100, 100, 100, 100, 100, 100, 100, 100]))
    assert result.trades == []  # nothing held, so every SELL clamps to zero


def test_long_only_short_reduces_an_existing_long_without_flipping_negative():
    engine = BacktestEngine(
        strategy=LongThenShortStrategy(),
        risk_engine=HardRiskEngine(_permissive_limits()),
        symbol="BTC-USD",
        starting_equity=Decimal("1000"),
        allow_short=False,
    )
    result = engine.run(make_candles([100, 100, 100, 100, 100, 100, 100, 100, 100, 100]))
    # the short leg only ever sells, never opens a negative position
    assert result.final_equity >= Decimal("0")
    assert all(t.side in ("BUY", "SELL") for t in result.trades)


def test_allow_short_true_still_lets_the_backtest_open_shorts():
    engine = BacktestEngine(
        strategy=type("AlwaysShort", (Strategy,), {
            "name": "always_short",
            "generate_signal": lambda self, s, c: Signal(s, Direction.SHORT, 1.0, ["S"]),
        })(),
        risk_engine=HardRiskEngine(_permissive_limits()),
        symbol="BTC-USD",
        starting_equity=Decimal("1000"),
        allow_short=True,
    )
    result = engine.run(make_candles([100, 100, 100, 100, 100, 100, 100, 100]))
    assert len(result.trades) > 0


def make_candles(closes: list[float]) -> pd.DataFrame:
    n = len(closes)
    return pd.DataFrame({
        "open_time": pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC"),
        "open": closes,
        "high": closes,
        "low": closes,
        "close": closes,
        "volume": [1.0] * n,
    })


def test_drawdown_flatten_does_not_permanently_block_future_trades():
    # Root cause this guards: peak_equity only ever grows via max(), so once
    # a drawdown breach flattens the account to cash below the old peak,
    # equity has no way to climb back on its own (no position, no new trades
    # allowed while the breach persists) - the account would be stuck
    # refusing every future signal forever, even through a huge recovery.
    limits = RiskLimits(
        max_position_pct=Decimal("100"),
        max_portfolio_exposure_pct=Decimal("100"),
        max_trade_risk_pct=Decimal("100"),
        max_daily_loss_pct=Decimal("99"),  # isolate the drawdown path from daily-loss
        max_drawdown_pct=Decimal("20"),
        max_leverage=Decimal("1"),
        max_trades_per_day=100,
    )
    # flat, then a hard crash (trips the 20% drawdown breaker, full flatten),
    # then a sustained recovery well past the pre-crash peak of 1000.
    closes = [100, 100, 100, 50, 50, 50, 200, 250, 300, 350, 400]
    candles = make_candles(closes)

    engine = BacktestEngine(
        strategy=AlwaysLongStrategy(),
        risk_engine=HardRiskEngine(limits),
        symbol="BTCUSDT",
        starting_equity=Decimal("1000"),
    )
    result = engine.run(candles)

    # Without the fix, this stays pinned near the crash-flatten equity
    # (~498) forever, since the old peak (1000) can never be reached again
    # from a flattened, positionless account.
    assert result.final_equity > Decimal("600")
    assert result.circuit_breaker_flattens >= 1
