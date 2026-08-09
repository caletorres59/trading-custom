from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from aurora.config import RiskLimits


class RiskDecisionType(str, Enum):
    APPROVE = "APPROVE"
    REDUCE = "REDUCE"
    REJECT = "REJECT"
    EMERGENCY_STOP = "EMERGENCY_STOP"


@dataclass(frozen=True)
class AccountState:
    equity: Decimal
    equity_at_day_start: Decimal
    peak_equity: Decimal
    daily_pnl: Decimal
    current_exposure_pct: Decimal  # % of equity already committed to open positions
    trades_today: int


@dataclass(frozen=True)
class TradeRequest:
    symbol: str
    direction: str  # "LONG" | "SHORT"
    stop_distance_pct: Decimal  # distance to stop-loss as % of entry price


@dataclass(frozen=True)
class RiskDecision:
    decision: RiskDecisionType
    approved_notional: Decimal
    reasons: list[str]


class HardRiskEngine:
    """Deterministic. No ML, no LLM, no strategy input into the limits
    themselves. This is the barrier from spec.md section 13: nothing
    downstream may execute without APPROVE/REDUCE from here, and nothing
    upstream (agent, portfolio manager, user request during automated
    operation) may alter these limits at runtime."""

    def __init__(self, limits: RiskLimits):
        self._limits = limits

    def check_kill_switch(self, account: AccountState) -> RiskDecision | None:
        """Daily-loss and drawdown checks, split out from evaluate() so the
        engine loop can run them on every price update - not only when a
        strategy happens to emit a new signal. A losing position that's
        already open must get flattened as soon as it breaches a limit,
        not whenever the strategy next feels like speaking up."""
        if account.equity_at_day_start > 0:
            daily_loss_pct = -(account.daily_pnl / account.equity_at_day_start) * Decimal("100")
            if daily_loss_pct >= self._limits.max_daily_loss_pct:
                return RiskDecision(
                    RiskDecisionType.EMERGENCY_STOP,
                    Decimal("0"),
                    [f"MAX_DAILY_LOSS_BREACHED:{daily_loss_pct:.4f}%"],
                )

        if account.peak_equity > 0:
            drawdown_pct = (account.peak_equity - account.equity) / account.peak_equity * Decimal("100")
            if drawdown_pct >= self._limits.max_drawdown_pct:
                return RiskDecision(
                    RiskDecisionType.EMERGENCY_STOP,
                    Decimal("0"),
                    [f"MAX_DRAWDOWN_BREACHED:{drawdown_pct:.4f}%"],
                )

        return None

    def evaluate(self, request: TradeRequest, account: AccountState) -> RiskDecision:
        kill_switch = self.check_kill_switch(account)
        if kill_switch is not None:
            return kill_switch

        if account.trades_today >= self._limits.max_trades_per_day:
            return RiskDecision(RiskDecisionType.REJECT, Decimal("0"), ["MAX_TRADES_PER_DAY_REACHED"])

        if request.stop_distance_pct <= 0:
            return RiskDecision(RiskDecisionType.REJECT, Decimal("0"), ["INVALID_STOP_DISTANCE"])

        remaining_exposure_pct = self._limits.max_portfolio_exposure_pct - account.current_exposure_pct
        if remaining_exposure_pct <= 0:
            return RiskDecision(RiskDecisionType.REJECT, Decimal("0"), ["MAX_PORTFOLIO_EXPOSURE_REACHED"])

        # Size so a full stop-out costs at most max_trade_risk_pct of equity.
        risk_budget = account.equity * (self._limits.max_trade_risk_pct / Decimal("100"))
        sized_notional = risk_budget / (request.stop_distance_pct / Decimal("100"))

        max_position_notional = account.equity * (self._limits.max_position_pct / Decimal("100"))
        max_exposure_notional = account.equity * (remaining_exposure_pct / Decimal("100"))

        capped_notional = min(sized_notional, max_position_notional, max_exposure_notional)

        if capped_notional <= 0:
            return RiskDecision(RiskDecisionType.REJECT, Decimal("0"), ["ZERO_SIZE_AFTER_LIMITS"])

        if capped_notional < sized_notional:
            return RiskDecision(RiskDecisionType.REDUCE, capped_notional, ["SIZE_REDUCED_BY_HARD_LIMIT"])

        return RiskDecision(RiskDecisionType.APPROVE, capped_notional, ["WITHIN_LIMITS"])
