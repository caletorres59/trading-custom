from __future__ import annotations

import pandas as pd

from aurora.strategy.base import Direction, Signal, Strategy


class VolatilitySpikeStrategy(Strategy):
    """Momentum-ignition: bets that an abnormally large candle (relative to
    recent volatility) marks the start of a fast continuation move, rather
    than waiting for a slow moving-average or channel signal to catch up.
    Trades in the direction the spike candle itself moved (close vs open).

    Optional regime filter: momentum-ignition only pays off when moves
    follow through. In a choppy, mean-reverting market the "spike" snaps
    back and the trade just bleeds fees. When ``er_period`` is set, a spike
    signal is suppressed unless the Kaufman efficiency ratio over the last
    ``er_period`` bars (net move / summed absolute moves; 0 = pure chop,
    1 = straight-line trend) is at least ``er_threshold``."""

    name = "volatility_spike"

    def __init__(
        self,
        window: int = 20,
        spike_multiplier: float = 2.0,
        min_confidence: float = 0.0,
        er_period: int = 0,
        er_threshold: float = 0.0,
    ):
        self.window = window
        self.spike_multiplier = spike_multiplier
        self.min_confidence = min_confidence
        self.er_period = er_period
        self.er_threshold = er_threshold

    def _efficiency_ratio(self, closes: pd.Series) -> float:
        net = abs(float(closes.iloc[-1]) - float(closes.iloc[-1 - self.er_period]))
        path = float(closes.diff().abs().iloc[-self.er_period:].sum())
        return net / path if path else 0.0

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        min_bars = max(self.window, self.er_period) + 2
        if len(candles) < min_bars:
            return Signal(symbol, Direction.NO_TRADE, 0.0, ["INSUFFICIENT_DATA"])

        ranges = candles["high"] - candles["low"]
        avg_range = ranges.iloc[-(self.window + 1):-1].mean()
        current = candles.iloc[-1]
        current_range = current["high"] - current["low"]

        if pd.isna(avg_range) or avg_range == 0:
            return Signal(symbol, Direction.NO_TRADE, 0.0, ["INSUFFICIENT_DATA"])

        spike_ratio = current_range / avg_range
        if spike_ratio < self.spike_multiplier:
            return Signal(symbol, Direction.NO_TRADE, 0.0, ["NO_SPIKE"])

        confidence = min(1.0, float((spike_ratio - self.spike_multiplier) / self.spike_multiplier))
        if confidence < self.min_confidence:
            return Signal(symbol, Direction.NO_TRADE, confidence, ["BELOW_MIN_CONFIDENCE"])

        if self.er_period and self._efficiency_ratio(candles["close"]) < self.er_threshold:
            return Signal(symbol, Direction.NO_TRADE, 0.0, ["CHOPPY_REGIME"])

        if current["close"] >= current["open"]:
            return Signal(symbol, Direction.LONG, confidence, ["VOLATILITY_SPIKE_UP"])
        return Signal(symbol, Direction.SHORT, confidence, ["VOLATILITY_SPIKE_DOWN"])
