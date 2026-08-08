from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

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
    fed via update_price(), minus a simulated taker fee."""

    def __init__(self, starting_equity: Decimal, quote_currency: str = "USDT"):
        self._cash = starting_equity
        self._peak_equity = starting_equity
        self._day = datetime.now(timezone.utc).date()
        self._equity_at_day_start = starting_equity
        self._positions: dict[str, Position] = {}
        self._last_price: dict[str, Decimal] = {}
        self._orders: dict[str, OrderResult] = {}
        self.quote_currency = quote_currency

    def update_price(self, symbol: str, price: Decimal) -> None:
        self._last_price[symbol] = price
        self._roll_day_if_needed()

    def _roll_day_if_needed(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._day:
            self._day = today
            self._equity_at_day_start = self._equity()

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

        self._peak_equity = max(self._peak_equity, self._equity())

        result = OrderResult(
            broker_order_id=str(uuid.uuid4()),
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            average_fill_price=fill_price,
            submitted_at=datetime.now(timezone.utc),
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
        )

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())
