import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import requests

from aurora.broker.alpaca_broker import (
    AlpacaBroker,
    from_alpaca_symbol,
    to_order_symbol,
    to_position_symbol,
)
from aurora.broker.base import Order, OrderSide, OrderStatus, OrderType


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.content = b"x" if payload is not None else b""

    def json(self):
        return self._payload

    @property
    def text(self):
        return json.dumps(self._payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err


class FakeSession:
    """Stands in for requests.Session. Canned Alpaca REST responses driven
    by mutable attributes the tests set up."""

    def __init__(self):
        self.headers = {}
        self.account = {"equity": "100000", "cash": "100000"}
        self.positions = []
        self.orders = []
        self.log = []
        self.reject_next_order = False
        self.next_fill = None  # (filled_qty, filled_avg_price)

    def request(self, method, url, timeout=None, params=None, json=None):
        self.log.append((method, url, params, json))
        if url.endswith("/v2/account"):
            return FakeResponse(self.account)
        if url.endswith("/v2/positions"):
            return FakeResponse(self.positions)
        if "/v2/orders/" in url:
            oid = url.rsplit("/", 1)[1]
            if method == "DELETE":
                return FakeResponse({})
            return FakeResponse(next(o for o in self.orders if o["id"] == oid))
        if url.endswith("/v2/orders"):
            if method == "GET":
                return FakeResponse(self.orders)
            if self.reject_next_order:
                return FakeResponse({"message": "insufficient balance for BTC"}, status=403)
            fq, fp = self.next_fill or (json["qty"], "79000")
            order = {
                "id": f"ord-{len(self.orders)}",
                "status": "filled",
                "filled_qty": str(fq),
                "filled_avg_price": str(fp),
                "filled_at": "2026-09-07T12:00:00Z",
                "symbol": json["symbol"],
                "side": json["side"],
                "qty": json["qty"],
            }
            self.orders.insert(0, order)
            return FakeResponse(order)
        raise AssertionError(f"unhandled {method} {url}")


def bookkeeping(**overrides):
    base = dict(
        cash=Decimal("100000"),
        peak_equity=Decimal("100000"),
        equity_at_day_start=Decimal("100000"),
        state_day="2026-09-07",
        trades_today=0,
        positions={},
    )
    base.update(overrides)
    return base


def make_broker(session, *, needs_seed=False, clock=None, **bk):
    return AlpacaBroker(
        key_id="k",
        secret_key="s",
        base_url="https://paper-api.alpaca.markets",
        bookkeeping=bookkeeping(**bk),
        needs_seed=needs_seed,
        session=session,
        clock=clock or (lambda: datetime(2026, 9, 7, 15, 0, tzinfo=timezone.utc)),
    )


def test_symbol_translation_round_trips():
    assert to_order_symbol("BTC-USD") == "BTC/USD"
    assert to_position_symbol("BTC-USD") == "BTCUSD"
    assert from_alpaca_symbol("BTCUSD") == "BTC-USD"
    assert from_alpaca_symbol("ETH/USD") == "ETH-USD"


def test_market_buy_parses_the_fill():
    session = FakeSession()
    session.next_fill = ("0.0002", "79149.1")
    broker = make_broker(session)

    result = broker.submit(
        Order(symbol="BTC-USD", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=Decimal("0.0002"))
    )

    assert result.status == OrderStatus.FILLED
    assert result.filled_quantity == Decimal("0.0002")
    assert result.average_fill_price == Decimal("79149.1")
    posted = [c for c in session.log if c[0] == "POST"][0][3]
    assert posted == {
        "symbol": "BTC/USD",
        "qty": "0.0002",
        "side": "buy",
        "type": "market",
        "time_in_force": "gtc",
    }


def test_rejected_order_returns_a_rejected_result_not_an_exception():
    session = FakeSession()
    session.reject_next_order = True
    broker = make_broker(session)

    result = broker.submit(
        Order(symbol="BTC-USD", side=OrderSide.SELL, order_type=OrderType.MARKET, quantity=Decimal("1"))
    )

    assert result.status == OrderStatus.REJECTED
    assert result.filled_quantity == Decimal("0")


def test_first_run_seeds_anchors_from_live_equity():
    session = FakeSession()
    session.account = {"equity": "99999.90", "cash": "99999.90"}
    # bookkeeping carries a placeholder that has nothing to do with this account
    broker = make_broker(session, needs_seed=True, peak_equity=Decimal("1000"),
                         equity_at_day_start=Decimal("1000"))

    snap = broker.get_account()

    assert snap.peak_equity == Decimal("99999.90")
    assert snap.daily_pnl == Decimal("0")


def test_stale_scale_bookkeeping_reseeds_at_cutover():
    # simulator-era row ($1k scale) against the new $100k paper account
    session = FakeSession()
    session.account = {"equity": "100000", "cash": "100000"}
    broker = make_broker(session, needs_seed=False, peak_equity=Decimal("1014.61"),
                         equity_at_day_start=Decimal("995.01"))

    snap = broker.get_account()

    assert snap.peak_equity == Decimal("100000")
    assert snap.daily_pnl == Decimal("0")


def test_stored_anchors_are_kept_when_not_seeding():
    session = FakeSession()
    session.account = {"equity": "100000", "cash": "100000"}
    broker = make_broker(session, peak_equity=Decimal("105000"),
                         equity_at_day_start=Decimal("98000"))

    snap = broker.get_account()

    assert snap.peak_equity == Decimal("105000")
    assert snap.daily_pnl == Decimal("2000")  # 100000 - 98000


def test_peak_equity_rises_but_never_falls_within_a_day():
    session = FakeSession()
    broker = make_broker(session)

    session.account = {"equity": "101000", "cash": "101000"}
    assert broker.get_account().peak_equity == Decimal("101000")

    session.account = {"equity": "100500", "cash": "100500"}
    assert broker.get_account().peak_equity == Decimal("101000")


def test_day_roll_reanchors_day_start_equity():
    session = FakeSession()
    day = {"now": datetime(2026, 9, 7, 23, 0, tzinfo=timezone.utc)}
    broker = make_broker(session, clock=lambda: day["now"], equity_at_day_start=Decimal("100000"))

    session.account = {"equity": "97000", "cash": "97000"}
    assert broker.get_account().daily_pnl == Decimal("-3000")

    day["now"] = datetime(2026, 9, 8, 0, 30, tzinfo=timezone.utc)
    snap = broker.get_account()
    assert snap.daily_pnl == Decimal("0")  # new day: start anchor reset to current equity


def test_reset_drawdown_baseline_reanchors_peak_to_current_equity():
    session = FakeSession()
    session.account = {"equity": "70000", "cash": "70000"}
    broker = make_broker(session, peak_equity=Decimal("100000"))

    broker.reset_drawdown_baseline()

    assert broker.get_account().peak_equity == Decimal("70000")


def test_trades_today_counts_only_filled_orders():
    session = FakeSession()
    session.orders = [
        {"id": "a", "filled_at": "2026-09-07T10:00:00Z"},
        {"id": "b", "filled_at": None},
        {"id": "c", "filled_at": "2026-09-07T11:00:00Z"},
    ]
    broker = make_broker(session)

    assert broker.get_account().trades_today == 2


def test_get_positions_maps_symbol_back_to_canonical():
    session = FakeSession()
    session.positions = [{"symbol": "BTCUSD", "qty": "0.5", "avg_entry_price": "79000"}]
    broker = make_broker(session)

    positions = broker.get_positions()

    assert len(positions) == 1
    assert positions[0].symbol == "BTC-USD"
    assert positions[0].quantity == Decimal("0.5")
    assert positions[0].average_entry_price == Decimal("79000")


def test_export_state_mirrors_alpaca_cash_and_positions():
    session = FakeSession()
    session.account = {"equity": "100500", "cash": "90000"}
    session.positions = [{"symbol": "BTCUSD", "qty": "0.13", "avg_entry_price": "80000"}]
    broker = make_broker(session)

    state = broker.export_state()

    assert state["cash"] == Decimal("90000")
    assert state["positions"] == {"BTC-USD": {"quantity": "0.13", "average_entry_price": "80000"}}
    assert state["state_day"] == "2026-09-07"


def test_missing_credentials_raise():
    with pytest.raises(RuntimeError):
        AlpacaBroker(key_id="", secret_key="s", base_url="x", bookkeeping=bookkeeping())
