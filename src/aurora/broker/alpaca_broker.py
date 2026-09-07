from __future__ import annotations

import logging
import time
from datetime import date, datetime, time as dtime, timezone
from decimal import Decimal
from typing import Callable

import requests

from aurora.broker.base import (
    AccountSnapshot,
    Order,
    OrderResult,
    OrderSide,
    OrderStatus,
    Position,
    TradingBroker,
)

logger = logging.getLogger("aurora.broker.alpaca")

# Alpaca crypto market orders fill within a second or two; poll a handful
# of times before giving up and reporting the order as still working.
_FILL_POLL_ATTEMPTS = 10
_FILL_POLL_INTERVAL_S = 0.5

_STATUS_MAP = {
    "filled": OrderStatus.FILLED,
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "new": OrderStatus.NEW,
    "accepted": OrderStatus.SUBMITTED,
    "pending_new": OrderStatus.SUBMITTED,
    "accepted_for_bidding": OrderStatus.SUBMITTED,
    "done_for_day": OrderStatus.SUBMITTED,
    "canceled": OrderStatus.CANCELED,
    "expired": OrderStatus.CANCELED,
    "rejected": OrderStatus.REJECTED,
}


def to_order_symbol(symbol: str) -> str:
    """Internal canonical (``BTC-USD``, Coinbase style) -> Alpaca order
    symbol (``BTC/USD``)."""
    return symbol.replace("-", "/")


def to_position_symbol(symbol: str) -> str:
    """Internal canonical -> Alpaca position path segment (``BTCUSD``)."""
    return symbol.replace("-", "")


def from_alpaca_symbol(symbol: str) -> str:
    """Alpaca's ``BTC/USD`` or ``BTCUSD`` -> internal canonical ``BTC-USD``.
    Only USD-quoted crypto pairs are in scope for this MVP."""
    if "/" in symbol:
        base, quote = symbol.split("/", 1)
        return f"{base}-{quote}"
    if symbol.endswith("USD"):
        return f"{symbol[:-3]}-USD"
    return symbol


def _fmt(quantity: Decimal) -> str:
    # Plain decimal string, never scientific notation (Alpaca rejects "2E-4").
    return format(quantity.normalize(), "f")


class AlpacaBroker(TradingBroker):
    """Live execution against Alpaca's REST API (paper or live endpoint,
    chosen by ``base_url``). Replaces the local PaperSimulatorBroker in the
    trading loop: orders, account and positions are Alpaca's real state,
    not a simulation.

    Alpaca does not track two numbers the HardRiskEngine needs - the
    reset-aware ``peak_equity`` (for the drawdown kill switch) and a
    start-of-UTC-day equity anchor (for the daily-loss kill switch) - so
    those are kept here and persisted via db.portfolio_store, exactly the
    way PaperSimulatorBroker's state was. Everything else (cash, positions,
    equity) is read live from Alpaca each call.

    Spot crypto cannot be shorted on Alpaca; the trading loop and backtest
    engines enforce that (a SELL is clamped to the held quantity) so this
    adapter never has to.
    """

    def __init__(
        self,
        key_id: str,
        secret_key: str,
        base_url: str,
        bookkeeping: dict,
        *,
        needs_seed: bool = False,
        session: requests.Session | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        if not key_id or not secret_key:
            raise RuntimeError("Alpaca API credentials are not configured")
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._session.headers.update(
            {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret_key}
        )
        self._clock = clock

        self._peak_equity = Decimal(str(bookkeeping["peak_equity"]))
        self._equity_at_day_start = Decimal(str(bookkeeping["equity_at_day_start"]))
        self._day = date.fromisoformat(bookkeeping["state_day"])
        # When the bookkeeping row didn't exist yet (first run after the
        # cut-over from the simulator), anchor peak / day-start to the real
        # Alpaca equity on the first get_account() rather than to a config
        # number that has nothing to do with this account.
        self._needs_seed = needs_seed
        self._seeded = False

    # ------------------------------------------------------------------ HTTP

    def _request(self, method: str, path: str, **kwargs) -> object:
        response = self._session.request(
            method, f"{self._base_url}{path}", timeout=15, **kwargs
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    # --------------------------------------------------------------- account

    def _refresh_anchors(self, equity: Decimal) -> None:
        today = self._clock().date()
        if self._needs_seed and not self._seeded:
            self._peak_equity = equity
            self._equity_at_day_start = equity
            self._day = today
            self._seeded = True
        elif today != self._day:
            self._day = today
            self._equity_at_day_start = equity
        self._peak_equity = max(self._peak_equity, equity)

    def _trades_today(self) -> int:
        midnight = datetime.combine(self._clock().date(), dtime.min, tzinfo=timezone.utc)
        orders = self._request(
            "GET",
            "/v2/orders",
            params={"status": "all", "after": midnight.isoformat(), "limit": 500},
        )
        return sum(1 for o in orders if o.get("filled_at"))

    def get_account(self) -> AccountSnapshot:
        acct = self._request("GET", "/v2/account")
        equity = Decimal(acct["equity"])
        self._refresh_anchors(equity)
        return AccountSnapshot(
            equity=equity,
            available_balance=Decimal(acct["cash"]),
            daily_pnl=equity - self._equity_at_day_start,
            peak_equity=self._peak_equity,
            trades_today=self._trades_today(),
        )

    def get_positions(self) -> list[Position]:
        raw = self._request("GET", "/v2/positions")
        return [
            Position(
                symbol=from_alpaca_symbol(p["symbol"]),
                quantity=Decimal(p["qty"]),
                average_entry_price=Decimal(p["avg_entry_price"]),
            )
            for p in raw
        ]

    def reset_drawdown_baseline(self) -> None:
        """Re-anchor peak_equity to current equity after a kill-switch
        flatten, so a max-drawdown trip is a temporary brake rather than a
        permanent one (see PaperSimulatorBroker.reset_drawdown_baseline for
        the full rationale - same bug class)."""
        acct = self._request("GET", "/v2/account")
        self._peak_equity = Decimal(acct["equity"])
        self._seeded = True

    def export_state(self) -> dict:
        acct = self._request("GET", "/v2/account")
        positions = self._request("GET", "/v2/positions")
        return {
            "cash": Decimal(acct["cash"]),
            "peak_equity": self._peak_equity,
            "equity_at_day_start": self._equity_at_day_start,
            "state_day": self._day.isoformat(),
            "trades_today": self._trades_today(),
            # Mirrored from Alpaca purely so the dashboard's portfolio_state
            # row stays populated the same way it was under the simulator.
            "positions": {
                from_alpaca_symbol(p["symbol"]): {
                    "quantity": p["qty"],
                    "average_entry_price": p["avg_entry_price"],
                }
                for p in positions
            },
        }

    # ----------------------------------------------------------------- orders

    def submit(self, order: Order) -> OrderResult:
        body = {
            "symbol": to_order_symbol(order.symbol),
            "qty": _fmt(order.quantity),
            "side": "buy" if order.side == OrderSide.BUY else "sell",
            "type": "market",
            "time_in_force": "gtc",  # crypto requires gtc or ioc, never day
        }
        try:
            resp = self._request("POST", "/v2/orders", json=body)
        except requests.HTTPError as exc:
            detail = exc.response.text[:300] if exc.response is not None else str(exc)
            logger.error(
                "alpaca_order_rejected symbol=%s side=%s qty=%s detail=%s",
                order.symbol, body["side"], body["qty"], detail,
            )
            return OrderResult(
                broker_order_id="",
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                average_fill_price=None,
                submitted_at=self._clock(),
            )

        order_id = resp["id"]
        for _ in range(_FILL_POLL_ATTEMPTS):
            if resp.get("status") in ("filled", "canceled", "rejected", "expired"):
                break
            time.sleep(_FILL_POLL_INTERVAL_S)
            resp = self._request("GET", f"/v2/orders/{order_id}")

        filled_qty = Decimal(resp.get("filled_qty") or "0")
        avg_price = resp.get("filled_avg_price")
        status = _STATUS_MAP.get(resp.get("status", ""), OrderStatus.SUBMITTED)
        if status not in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED) and filled_qty > 0:
            status = OrderStatus.PARTIALLY_FILLED
        if status == OrderStatus.SUBMITTED:
            logger.warning(
                "alpaca_order_unconfirmed id=%s status=%s filled_qty=%s",
                order_id, resp.get("status"), filled_qty,
            )
        return OrderResult(
            broker_order_id=order_id,
            status=status,
            filled_quantity=filled_qty,
            average_fill_price=Decimal(avg_price) if avg_price else None,
            submitted_at=self._clock(),
        )

    def cancel(self, broker_order_id: str) -> None:
        try:
            self._request("DELETE", f"/v2/orders/{broker_order_id}")
        except requests.HTTPError:
            pass  # already terminal - nothing to cancel

    def get_status(self, broker_order_id: str) -> OrderStatus:
        resp = self._request("GET", f"/v2/orders/{broker_order_id}")
        return _STATUS_MAP.get(resp.get("status", ""), OrderStatus.SUBMITTED)
