from decimal import Decimal

import pandas as pd

from aurora.risk.watchdogs import (
    AccountConsistencyWatchdog,
    DataIntegrityWatchdog,
    VolatilityRegimeWatchdog,
    blocking_failure,
    run_watchdogs,
)


def make_candles(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"close": closes})


def test_data_integrity_passes_on_normal_move():
    watchdog = DataIntegrityWatchdog()
    report = watchdog.check(make_candles([100.0, 101.0]))
    assert report.passed
    assert report.blocking


def test_data_integrity_blocks_on_absurd_single_bar_move():
    watchdog = DataIntegrityWatchdog(max_single_bar_move_pct=Decimal("25"))
    report = watchdog.check(make_candles([100.0, 150.0]))  # +50% in one bar
    assert not report.passed
    assert report.blocking


def test_data_integrity_blocks_on_non_positive_price():
    watchdog = DataIntegrityWatchdog()
    report = watchdog.check(make_candles([100.0, 0.0]))
    assert not report.passed


def test_account_consistency_passes_when_reconciled():
    watchdog = AccountConsistencyWatchdog()
    report = watchdog.check(reported_equity=Decimal("1000"), cash=Decimal("500"), positions_notional=Decimal("500"))
    assert report.passed
    assert report.blocking


def test_account_consistency_blocks_on_mismatch():
    watchdog = AccountConsistencyWatchdog(tolerance_pct=Decimal("0.5"))
    # reported 1000 vs recomputed 900 -> 10% drift, well over tolerance
    report = watchdog.check(reported_equity=Decimal("1000"), cash=Decimal("500"), positions_notional=Decimal("400"))
    assert not report.passed
    assert report.blocking


def test_volatility_regime_is_advisory_not_blocking():
    watchdog = VolatilityRegimeWatchdog(lookback=5, extreme_std_multiplier=Decimal("3"))
    # a calm baseline followed by a violent recent stretch
    closes = [100.0] * 30 + [100.0, 130.0, 90.0, 140.0, 80.0, 150.0]
    report = watchdog.check(make_candles(closes))
    assert report.blocking is False  # never blocks regardless of passed/failed


def test_run_watchdogs_only_blocking_failures_stop_the_trade():
    closes = [100.0] * 25 + [101.0]
    reports = run_watchdogs(
        candles=make_candles(closes),
        reported_equity=Decimal("1000"),
        cash=Decimal("500"),
        positions_notional=Decimal("500"),
    )
    assert blocking_failure(reports) is None


def test_run_watchdogs_flags_blocking_failure():
    closes = [100.0, 200.0]  # +100% single bar, trips data integrity
    reports = run_watchdogs(
        candles=make_candles(closes),
        reported_equity=Decimal("1000"),
        cash=Decimal("500"),
        positions_notional=Decimal("500"),
    )
    blocker = blocking_failure(reports)
    assert blocker is not None
    assert blocker.name == "data_integrity"
