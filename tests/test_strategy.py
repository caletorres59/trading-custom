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


from aurora.strategy.volatility_spike import VolatilitySpikeStrategy


def _spike_frame(closes):
    n = len(closes)
    df = pd.DataFrame({
        "open": [c - 0.1 for c in closes],
        "high": [c + 3 for c in closes],
        "low": [c - 3 for c in closes],
        "close": closes,
    })
    # make the last bar an unmistakable spike (range >> the ~6-wide baseline)
    df.loc[df.index[-1], ["high", "low"]] = [closes[-1] + 60, closes[-1] - 1]
    return df


def test_volatility_spike_fires_on_a_clean_trend():
    strat = VolatilitySpikeStrategy(window=20, spike_multiplier=3.0, er_period=30, er_threshold=0.30)
    signal = strat.generate_signal("BTC-USD", _spike_frame(list(range(100, 160))))
    assert signal.direction == Direction.LONG
    assert "VOLATILITY_SPIKE_UP" in signal.reason_codes


def test_volatility_spike_regime_filter_suppresses_a_spike_in_chop():
    strat = VolatilitySpikeStrategy(window=20, spike_multiplier=3.0, er_period=30, er_threshold=0.30)
    choppy = [100 + (4 if i % 2 else -4) for i in range(60)]
    signal = strat.generate_signal("BTC-USD", _spike_frame(choppy))
    assert signal.direction == Direction.NO_TRADE
    assert "CHOPPY_REGIME" in signal.reason_codes


def test_volatility_spike_regime_filter_off_by_default():
    strat = VolatilitySpikeStrategy(window=20, spike_multiplier=3.0)  # er_period defaults to 0
    choppy = [100 + (4 if i % 2 else -4) for i in range(60)]
    signal = strat.generate_signal("BTC-USD", _spike_frame(choppy))
    assert signal.direction in (Direction.LONG, Direction.SHORT)  # filter inert, spike still trades
