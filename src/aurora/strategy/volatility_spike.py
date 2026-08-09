from __future__ import annotations

import pandas as pd

from aurora.strategy.base import Direction, Signal, Strategy


class VolatilitySpikeStrategy(Strategy):
    """Momentum-ignition: bets that an abnormally large candle (relative to
    recent volatility) marks the start of a fast continuation move, rather
    than waiting for a slow moving-average or channel signal to catch up.
    Trades in the direction the spike candle itself moved (close vs open)."""

    name = "volatility_spike"

    def __init__(self, window: int = 20, spike_multiplier: float = 2.0, min_confidence: float = 0.0):
        self.window = window
        self.spike_multiplier = spike_multiplier
        self.min_confidence = min_confidence

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        if len(candles) < self.window + 2:
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

        if current["close"] >= current["open"]:
            return Signal(symbol, Direction.LONG, confidence, ["VOLATILITY_SPIKE_UP"])
        return Signal(symbol, Direction.SHORT, confidence, ["VOLATILITY_SPIKE_DOWN"])
