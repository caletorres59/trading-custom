from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Callable

from aurora.broker.base import (
    AccountSnapshot,
    Order,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    TradingBroker,
)

TAKER_FEE_RATE = Decimal("0.001")  # 0.1%, matches typical spot exchange taker fee


class PaperSimulatorBroker(TradingBroker):
    """Local fill simulator: no network calls, fake money. Mirrors the
    spec's PaperBroker. Market orders fill instantly at the last price
    fed via update_price(), minus a simulated taker fee.

    Takes its starting state explicitly (see db.portfolio_store) instead
    of always starting from starting_equity, so it can resume correctly
    across ephemeral runs (e.g. one process per GitHub Actions run) that
    don't share memory with each other.

    `clock` defaults to wall-clock time (live trading) but can be swapped
    for a simulated clock so a backtest's day-rollover (daily loss reset,
    trades-per-day reset) tracks simulated historical time instead of the
    real current date."""

    def __init__(
        self,
        state: dict,
        quote_currency: str = "USDT",
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._cash: Decimal = state["cash"]
        self._peak_equity: Decimal = state["peak_equity"]
        self._equity_at_day_start: Decimal = state["equity_at_day_start"]
        self._day: date = date.fromisoformat(state["state_day"])
        self.trades_today: int = state["trades_today"]
        self._positions: dict[str, Position] = {
            symbol: Position(symbol, Decimal(p["quantity"]), Decimal(p["average_entry_price"]))
            for symbol, p in state["positions"].items()
        }
        self._last_price: dict[str, Decimal] = {}
        self._orders: dict[str, OrderResult] = {}
        self.quote_currency = quote_currency
        self._clock = clock

    def update_price(self, symbol: str, price: Decimal) -> None:
        self._last_price[symbol] = price
        self._roll_day_if_needed()
        self._peak_equity = max(self._peak_equity, self._equity())

    def _roll_day_if_needed(self) -> None:
        today = self._clock().date()
        if today != self._day:
            self._day = today
            self._equity_at_day_start = self._equity()
            self.trades_today = 0

    def _equity(self) -> Decimal:
        equity = self._cash
        for symbol, position in self._positions.items():
            price = self._last_price.get(symbol, position.average_entry_price)
            equity += position.quantity * price
        return equity

    def submit(self, order: Order) -> OrderResult:
        if order.symbol not in self._last_price:
            raise RuntimeError(f"No reference price for {order.symbol}; call update_price first")

        if order.order_type != OrderType.MARKET and order.price is not None:
            fill_price = order.price
        else:
            fill_price = self._last_price[order.symbol]

        notional = order.quantity * fill_price
        fee = notional * TAKER_FEE_RATE

        position = self._positions.get(order.symbol, Position(order.symbol, Decimal("0"), fill_price))

        if order.side == OrderSide.BUY:
            self._cash -= notional + fee
            new_qty = position.quantity + order.quantity
        else:
            self._cash += notional - fee
            new_qty = position.quantity - order.quantity

        if new_qty == 0:
            self._positions.pop(order.symbol, None)
        else:
            self._positions[order.symbol] = Position(order.symbol, new_qty, fill_price)

        self.trades_today += 1

        result = OrderResult(
            broker_order_id=str(uuid.uuid4()),
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            average_fill_price=fill_price,
            submitted_at=self._clock(),
        )
        self._orders[result.broker_order_id] = result
        return result

    def cancel(self, broker_order_id: str) -> None:
        return None  # market orders fill instantly in this simulator; nothing to cancel

    def get_status(self, broker_order_id: str) -> OrderStatus:
        return self._orders[broker_order_id].status

    def get_account(self) -> AccountSnapshot:
        self._roll_day_if_needed()
        equity = self._equity()
        daily_pnl = equity - self._equity_at_day_start
        return AccountSnapshot(
            equity=equity,
            available_balance=self._cash,
            daily_pnl=daily_pnl,
            peak_equity=self._peak_equity,
            trades_today=self.trades_today,
        )

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    def export_state(self) -> dict:
        return {
            "cash": self._cash,
            "peak_equity": self._peak_equity,
            "equity_at_day_start": self._equity_at_day_start,
            "state_day": self._day.isoformat(),
            "trades_today": self.trades_today,
            "positions": {
                symbol: {
                    "quantity": str(position.quantity),
                    "average_entry_price": str(position.average_entry_price),
                }
                for symbol, position in self._positions.items()
            },
        }
