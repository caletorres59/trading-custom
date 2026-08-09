from decimal import Decimal

from aurora.broker.base import Order, OrderSide, OrderType
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


def market_order(side: OrderSide, quantity: str) -> Order:
    return Order(symbol="BTCUSDT", side=side, order_type=OrderType.MARKET, quantity=Decimal(quantity))


def test_average_entry_price_is_weighted_average_when_adding_to_position():
    # Two BUYs at different prices must blend into a weighted average, not
    # just take the latest fill price.
    broker = PaperSimulatorBroker(make_state())
    broker.update_price("BTCUSDT", Decimal("100"))
    broker.submit(market_order(OrderSide.BUY, "1"))  # 1 @ 100

    broker.update_price("BTCUSDT", Decimal("200"))
    broker.submit(market_order(OrderSide.BUY, "1"))  # 1 @ 200

    position = broker.get_positions()[0]
    assert position.quantity == Decimal("2")
    assert position.average_entry_price == Decimal("150")  # (1*100 + 1*200) / 2


def test_average_entry_price_unchanged_on_partial_close():
    # Selling part of a position must not overwrite the cost basis of the
    # shares that remain open with the exit fill price.
    broker = PaperSimulatorBroker(make_state())
    broker.update_price("BTCUSDT", Decimal("100"))
    broker.submit(market_order(OrderSide.BUY, "2"))  # 2 @ 100

    broker.update_price("BTCUSDT", Decimal("500"))
    broker.submit(market_order(OrderSide.SELL, "1"))  # sell 1 @ 500, 1 remains

    position = broker.get_positions()[0]
    assert position.quantity == Decimal("1")
    assert position.average_entry_price == Decimal("100")


def test_average_entry_price_resets_when_flipping_through_zero():
    # Selling more than the current long resets the cost basis for the new
    # (short) side to the fill price, not a blend with the closed-out long.
    broker = PaperSimulatorBroker(make_state())
    broker.update_price("BTCUSDT", Decimal("100"))
    broker.submit(market_order(OrderSide.BUY, "1"))  # long 1 @ 100

    broker.update_price("BTCUSDT", Decimal("300"))
    broker.submit(market_order(OrderSide.SELL, "3"))  # closes long, opens short 2 @ 300

    position = broker.get_positions()[0]
    assert position.quantity == Decimal("-2")
    assert position.average_entry_price == Decimal("300")
