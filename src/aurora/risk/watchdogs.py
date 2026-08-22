from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd


@dataclass(frozen=True)
class WatchdogReport:
    name: str
    passed: bool
    blocking: bool
    reason: str


class DataIntegrityWatchdog:
    """Blocks a trade if the triggering candle looks broken: a
    non-positive close, or a single-bar move so large it's more likely a
    bad tick/API glitch than a real price."""

    name = "data_integrity"

    def __init__(self, max_single_bar_move_pct: Decimal = Decimal("25")):
        self._max_move = max_single_bar_move_pct

    def check(self, candles: pd.DataFrame) -> WatchdogReport:
        if len(candles) < 2:
            return WatchdogReport(self.name, True, True, "not enough candles to check")
        last_close = Decimal(str(candles["close"].iloc[-1]))
        prev_close = Decimal(str(candles["close"].iloc[-2]))
        if last_close <= 0 or prev_close <= 0:
            return WatchdogReport(self.name, False, True, "non-positive price in candle data")
        move_pct = abs(last_close - prev_close) / prev_close * Decimal("100")
        if move_pct > self._max_move:
            return WatchdogReport(
                self.name, False, True,
                f"single-bar move {move_pct:.2f}% exceeds {self._max_move}% sanity bound",
            )
        return WatchdogReport(self.name, True, True, f"single-bar move {move_pct:.2f}% within bound")


class AccountConsistencyWatchdog:
    """Blocks a trade if equity recomputed independently from raw cash +
    positions doesn't match what the broker reported, within tolerance.
    Guards against a repeat of past silent state bugs (stale peak_equity,
    wrong average_entry_price) now that position sizes are much larger
    and a miscalculation would be far more costly."""

    name = "account_consistency"

    def __init__(self, tolerance_pct: Decimal = Decimal("0.5")):
        self._tolerance = tolerance_pct

    def check(self, reported_equity: Decimal, cash: Decimal, positions_notional: Decimal) -> WatchdogReport:
        recomputed_equity = cash + positions_notional
        if reported_equity == 0:
            return WatchdogReport(self.name, True, True, "zero equity, nothing to reconcile")
        drift_pct = abs(recomputed_equity - reported_equity) / reported_equity * Decimal("100")
        if drift_pct > self._tolerance:
            return WatchdogReport(
                self.name, False, True,
                f"equity mismatch: reported {reported_equity} vs recomputed {recomputed_equity} ({drift_pct:.2f}% drift)",
            )
        return WatchdogReport(self.name, True, True, f"equity reconciled within {drift_pct:.2f}% drift")


class VolatilityRegimeWatchdog:
    """Advisory only, never blocks. Flags when recent realized volatility
    is well outside the session's own baseline, so an aggressively-sized
    trade during an unprecedented regime still gets logged loudly for a
    human to notice - without re-imposing the conservative caps the
    project deliberately moved away from."""

    name = "volatility_regime"

    def __init__(self, lookback: int = 20, extreme_std_multiplier: Decimal = Decimal("3")):
        self._lookback = lookback
        self._extreme_multiplier = extreme_std_multiplier

    def check(self, candles: pd.DataFrame) -> WatchdogReport:
        closes = candles["close"].astype(float)
        if len(closes) < self._lookback + 2:
            return WatchdogReport(self.name, True, False, "not enough history to assess regime")
        returns = closes.pct_change().dropna()
        recent_std = returns.tail(self._lookback).std()
        baseline_std = returns.std()
        if not baseline_std:
            return WatchdogReport(self.name, True, False, "baseline volatility is zero")
        ratio = recent_std / baseline_std
        if ratio > float(self._extreme_multiplier):
            return WatchdogReport(
                self.name, False, False,
                f"recent volatility {ratio:.1f}x the session baseline - unprecedented regime, logged for visibility only",
            )
        return WatchdogReport(self.name, True, False, f"recent volatility {ratio:.1f}x baseline, within range")


def run_watchdogs(
    candles: pd.DataFrame,
    reported_equity: Decimal,
    cash: Decimal,
    positions_notional: Decimal,
) -> list[WatchdogReport]:
    """Runs all three watchdogs and returns their reports. Callers should
    block the trade if any *blocking* report has passed=False; advisory
    (non-blocking) reports are for audit-trail visibility only."""
    return [
        DataIntegrityWatchdog().check(candles),
        AccountConsistencyWatchdog().check(reported_equity, cash, positions_notional),
        VolatilityRegimeWatchdog().check(candles),
    ]


def blocking_failure(reports: list[WatchdogReport]) -> WatchdogReport | None:
    for report in reports:
        if report.blocking and not report.passed:
            return report
    return None
