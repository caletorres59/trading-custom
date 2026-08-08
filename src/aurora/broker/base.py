from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class Order:
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    client_order_id: str | None = None


@dataclass(frozen=True)
class OrderResult:
    broker_order_id: str
    status: OrderStatus
    filled_quantity: Decimal
    average_fill_price: Decimal | None
    submitted_at: datetime


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal


@dataclass(frozen=True)
class AccountSnapshot:
    equity: Decimal
    available_balance: Decimal
    daily_pnl: Decimal
    peak_equity: Decimal
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TradingBroker(ABC):
    """Mirrors spec.md section 18. Every implementation (paper, testnet,
    live) must expose exactly this surface so the engine never needs to
    know which one it's talking to."""

    @abstractmethod
    def submit(self, order: Order) -> OrderResult: ...

    @abstractmethod
    def cancel(self, broker_order_id: str) -> None: ...

    @abstractmethod
    def get_status(self, broker_order_id: str) -> OrderStatus: ...

    @abstractmethod
    def get_account(self) -> AccountSnapshot: ...

    @abstractmethod
    def get_positions(self) -> list[Position]: ...
