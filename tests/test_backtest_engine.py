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
