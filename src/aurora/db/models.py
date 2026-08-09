from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SignalRecord(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    correlation_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String)
    strategy: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column()
    reason_codes: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RiskDecisionRecord(Base):
    __tablename__ = "risk_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    correlation_id: Mapped[str] = mapped_column(String, index=True)
    decision: Mapped[str] = mapped_column(String)
    approved_notional: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    reasons: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OrderRecord(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    correlation_id: Mapped[str] = mapped_column(String, index=True)
    broker_order_id: Mapped[str] = mapped_column(String)
    symbol: Mapped[str] = mapped_column(String)
    side: Mapped[str] = mapped_column(String)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    fill_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PortfolioState(Base):
    """Single-row table holding the paper broker's account state, so it
    survives across ephemeral runs (one process per scheduled execution)
    instead of living only in memory."""

    __tablename__ = "portfolio_state"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    peak_equity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    equity_at_day_start: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    state_day: Mapped[str] = mapped_column(String)
    trades_today: Mapped[int] = mapped_column(Integer, default=0)
    positions_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class EquitySnapshot(Base):
    """One row per run_once(), so the dashboard has a real time series to
    chart instead of only ever seeing the latest PortfolioState."""

    __tablename__ = "equity_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    peak_equity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    daily_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    correlation_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
