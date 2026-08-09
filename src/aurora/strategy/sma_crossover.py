from __future__ import annotations

import pandas as pd

from aurora.strategy.base import Direction, Signal, Strategy


class SmaCrossoverStrategy(Strategy):
    """Baseline trend-following strategy per spec Phase 4: prove a simple,
    dumb edge exists before adding any ML/LLM agent on top of it."""

    name = "sma_crossover"

    def __init__(self, fast_period: int = 20, slow_period: int = 50, min_confidence: float = 0.0):
        if fast_period >= slow_period:
            raise ValueError("fast_period must be < slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.min_confidence = min_confidence

    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal:
        if len(candles) < self.slow_period + 1:
            return Signal(symbol, Direction.NO_TRADE, 0.0, ["INSUFFICIENT_DATA"])

        close = candles["close"]
        fast = close.rolling(self.fast_period).mean()
        slow = close.rolling(self.slow_period).mean()

        fast_now, fast_prev = fast.iloc[-1], fast.iloc[-2]
        slow_now, slow_prev = slow.iloc[-1], slow.iloc[-2]

        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now

        separation = abs(fast_now - slow_now) / slow_now
        confidence = min(1.0, float(separation) * 20)

        if (crossed_up or crossed_down) and confidence < self.min_confidence:
            return Signal(symbol, Direction.NO_TRADE, confidence, ["BELOW_MIN_CONFIDENCE"])
        if crossed_up:
            return Signal(symbol, Direction.LONG, confidence, ["SMA_CROSS_UP"])
        if crossed_down:
            return Signal(symbol, Direction.SHORT, confidence, ["SMA_CROSS_DOWN"])
        return Signal(symbol, Direction.NO_TRADE, 0.0, ["NO_CROSSOVER"])
