from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from aurora.db.models import PortfolioState
from aurora.db.session import session_scope

STATE_ID = "default"  # single portfolio for this MVP; one row is enough


def load_portfolio_state(
    session_factory: sessionmaker, starting_equity: Decimal
) -> tuple[dict, bool]:
    """Returns ``(state, needs_seed)``. ``needs_seed`` is True when no row
    existed yet, so a live broker knows to anchor its peak / day-start
    equity to the real account balance instead of the config placeholder."""
    with session_scope(session_factory) as session:
        row = session.get(PortfolioState, STATE_ID)
        if row is None:
            return {
                "cash": starting_equity,
                "peak_equity": starting_equity,
                "equity_at_day_start": starting_equity,
                "state_day": date.today().isoformat(),
                "trades_today": 0,
                "positions": {},
            }, True
        return {
            "cash": row.cash,
            "peak_equity": row.peak_equity,
            "equity_at_day_start": row.equity_at_day_start,
            "state_day": row.state_day,
            "trades_today": row.trades_today,
            "positions": json.loads(row.positions_json),
        }, False


def save_portfolio_state(session_factory: sessionmaker, state: dict) -> None:
    with session_scope(session_factory) as session:
        row = session.get(PortfolioState, STATE_ID)
        if row is None:
            row = PortfolioState(id=STATE_ID)
            session.add(row)
        row.cash = state["cash"]
        row.peak_equity = state["peak_equity"]
        row.equity_at_day_start = state["equity_at_day_start"]
        row.state_day = state["state_day"]
        row.trades_today = state["trades_today"]
        row.positions_json = json.dumps(state["positions"])
