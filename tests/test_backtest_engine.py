from decimal import Decimal

import pandas as pd

from aurora.backtest.engine import BacktestEngine
from aurora.config import RiskLimits
from aurora.risk.risk_engine import HardRiskEngine
from aurora.risk.trailing_stop import TrailingStopConfig
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


class BuyOnceStrategy(Strategy):
    """Enters LONG on the first bar it's asked about, then goes quiet -
    isolates the trailing-stop manager as the only thing that can still
    act on the position afterward."""

    name = "buy_once"

    def __init__(self):
        self.bought = False

    def generate_signal(self, symbol, candles):
        if not self.bought:
            self.bought = True
            return Signal(symbol, Direction.LONG, 1.0, ["ENTRY"])
        return Signal(symbol, Direction.NO_TRADE, 0.0, ["HOLD"])


def test_trailing_stop_exits_a_winner_after_it_pulls_back_from_its_high():
    # Entry ~100, runs up to 110 (past the 3% activation), pulls back to
    # 108.5 (not far enough off the 110 high-water mark yet), then to 107
    # (past the 2% trail off 110 = 107.8) -> exit, without the strategy
    # ever emitting another signal.
    engine = BacktestEngine(
        strategy=BuyOnceStrategy(),
        risk_engine=HardRiskEngine(_permissive_limits()),
        symbol="BTC-USD",
        starting_equity=Decimal("1000"),
        allow_short=False,
        exits=TrailingStopConfig(
            enabled=True, stop_loss_pct=Decimal("0"), trail_activation_pct=Decimal("3"), trail_pct=Decimal("2")
        ),
    )
    result = engine.run(make_candles([100, 100, 100, 110, 108.5, 107]))

    exit_trades = [t for t in result.trades if t.direction == "TRAILING_STOP"]
    assert len(exit_trades) == 1
    assert exit_trades[0].side == "SELL"
    assert result.trailing_stop_exits == 1


def test_trailing_stop_disabled_by_default_never_exits_on_its_own():
    engine = BacktestEngine(
        strategy=BuyOnceStrategy(),
        risk_engine=HardRiskEngine(_permissive_limits()),
        symbol="BTC-USD",
        starting_equity=Decimal("1000"),
        allow_short=False,
    )
    result = engine.run(make_candles([100, 100, 100, 110, 108.5, 60]))  # even a big crash

    assert result.trailing_stop_exits == 0
    assert all(t.risk_decision != "TRAILING_EXIT" for t in result.trades)


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
