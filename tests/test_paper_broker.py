from decimal import Decimal

from aurora.broker.paper_broker import PaperSimulatorBroker


def make_state(**overrides):
    defaults = dict(
        cash=Decimal("1000"),
        peak_equity=Decimal("1000"),
        equity_at_day_start=Decimal("1000"),
        state_day="2026-08-09",
        trades_today=0,
        positions={},
    )
    defaults.update(overrides)
    return defaults


def test_peak_equity_tracks_mark_to_market_gains_with_no_trade():
    # A held position that gains value on a price update alone (no submit())
    # must still raise peak_equity, since drawdown_pct is measured against it.
    broker = PaperSimulatorBroker(
        make_state(
            cash=Decimal("500"),
            peak_equity=Decimal("1000"),
            positions={"BTCUSDT": {"quantity": "0.01", "average_entry_price": "50000"}},
        )
    )

    broker.update_price("BTCUSDT", Decimal("60000"))  # equity: 500 + 0.01*60000 = 1100

    assert broker.get_account().peak_equity == Decimal("1100")


def test_peak_equity_never_decreases_on_price_drop():
    broker = PaperSimulatorBroker(
        make_state(
            cash=Decimal("500"),
            peak_equity=Decimal("1000"),
            positions={"BTCUSDT": {"quantity": "0.01", "average_entry_price": "50000"}},
        )
    )

    broker.update_price("BTCUSDT", Decimal("40000"))  # equity: 500 + 0.01*40000 = 900, below peak

    assert broker.get_account().peak_equity == Decimal("1000")
