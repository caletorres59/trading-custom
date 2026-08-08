import pandas as pd
import pytest

from aurora.strategy.base import Direction
from aurora.strategy.sma_crossover import SmaCrossoverStrategy


def make_candles(closes):
    return pd.DataFrame({"close": closes})


def test_no_trade_with_insufficient_data():
    strategy = SmaCrossoverStrategy(fast_period=3, slow_period=5)
    candles = make_candles([100, 101, 102])
    signal = strategy.generate_signal("BTCUSDT", candles)
    assert signal.direction == Direction.NO_TRADE
    assert "INSUFFICIENT_DATA" in signal.reason_codes


def test_detects_bullish_crossover():
    strategy = SmaCrossoverStrategy(fast_period=2, slow_period=4)
    # Fast SMA sits below slow SMA, then a sharp move flips it above.
    closes = [100, 99, 98, 97, 96, 95, 120]
    candles = make_candles(closes)
    signal = strategy.generate_signal("BTCUSDT", candles)
    assert signal.direction == Direction.LONG
    assert "SMA_CROSS_UP" in signal.reason_codes


def test_no_crossover_returns_no_trade():
    strategy = SmaCrossoverStrategy(fast_period=2, slow_period=4)
    closes = [100, 100, 100, 100, 100, 100, 100]
    candles = make_candles(closes)
    signal = strategy.generate_signal("BTCUSDT", candles)
    assert signal.direction == Direction.NO_TRADE
    assert "NO_CROSSOVER" in signal.reason_codes


def test_rejects_invalid_period_configuration():
    with pytest.raises(ValueError):
        SmaCrossoverStrategy(fast_period=10, slow_period=5)
