from __future__ import annotations

import pandas as pd

from aurora.strategy.base import Direction, Signal, Strategy


class BreakoutStrategy(Strategy):
    """Donchian-channel breakout: bets that a fresh high/low outside the
    recent trading range marks the start of a new directional move -
    the opposite read of the same event from MeanReversionStrategy,
    which bets a stretched price snaps back instead."""

    name = "breakout"

    def __init__(self, window: int = 20, min_confidence: float = 0.0):
        self.window = window
        self.min_confidence = min_confidence

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        if len(candles) < self.window + 1:
            return Signal(symbol, Direction.NO_TRADE, 0.0, ["INSUFFICIENT_DATA"])

        prior = candles.iloc[-(self.window + 1):-1]
        channel_high = prior["high"].max()
        channel_low = prior["low"].min()
        channel_width = channel_high - channel_low
        price = candles["close"].iloc[-1]

        if channel_width == 0 or pd.isna(channel_width):
            return Signal(symbol, Direction.NO_TRADE, 0.0, ["INSUFFICIENT_DATA"])

        if price > channel_high:
            confidence = min(1.0, float((price - channel_high) / channel_width))
            if confidence < self.min_confidence:
                return Signal(symbol, Direction.NO_TRADE, confidence, ["BELOW_MIN_CONFIDENCE"])
            return Signal(symbol, Direction.LONG, confidence, ["BREAKOUT_UP"])
        if price < channel_low:
            confidence = min(1.0, float((channel_low - price) / channel_width))
            if confidence < self.min_confidence:
                return Signal(symbol, Direction.NO_TRADE, confidence, ["BELOW_MIN_CONFIDENCE"])
            return Signal(symbol, Direction.SHORT, confidence, ["BREAKOUT_DOWN"])
        return Signal(symbol, Direction.NO_TRADE, 0.0, ["WITHIN_RANGE"])
