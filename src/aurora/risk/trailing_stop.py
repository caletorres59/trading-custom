from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TrailingStopConfig:
    """Roadmap idea #3 ("asymmetric exits / let winners run"): today every
    position is opened and closed by the same symmetric strategy signal, so
    a rare big winner gets cut exactly as fast as a loser. This adds two
    independent, deterministic exit triggers evaluated every tick
    (independent of whether the strategy currently emits a signal, the same
    way the kill switch is) - no ML, no LLM, matches the project's Hard Risk
    Engine philosophy (spec.md Regla 1).

    - ``stop_loss_pct``: cut losers fast - exit if price falls this far
      below the position's entry price, no matter what.
    - ``trail_activation_pct`` / ``trail_pct``: let winners run - trailing
      doesn't start until the position is up ``trail_activation_pct`` from
      entry; once active, exit if price pulls back ``trail_pct`` from the
      highest price seen since entry, locking in the rest of the move
      instead of round-tripping it back to breakeven or a loss."""

    enabled: bool = False
    stop_loss_pct: Decimal = Decimal("0")
    trail_activation_pct: Decimal = Decimal("0")
    trail_pct: Decimal = Decimal("0")


@dataclass(frozen=True)
class TrailingStopDecision:
    should_exit: bool
    reason: str | None
    high_water_price: Decimal  # updated watermark to persist for the next tick


class TrailingStopEngine:
    """Long-only (matches the spot long-only constraint elsewhere in this
    project - see ``allow_short``). Stateless itself; the caller is
    responsible for persisting ``high_water_price`` between ticks (in the
    backtest, an in-memory dict; live, a DB row - see db.portfolio_store)
    and for resetting it to the fresh fill price whenever a position opens
    from flat."""

    def __init__(self, config: TrailingStopConfig):
        self.config = config

    def evaluate(
        self,
        current_price: Decimal,
        entry_price: Decimal,
        high_water_price: Decimal | None,
    ) -> TrailingStopDecision:
        hwm = max(high_water_price or entry_price, current_price)

        if not self.config.enabled or entry_price <= 0:
            return TrailingStopDecision(False, None, hwm)

        if self.config.stop_loss_pct > 0:
            stop_loss_price = entry_price * (Decimal("1") - self.config.stop_loss_pct / Decimal("100"))
            if current_price <= stop_loss_price:
                return TrailingStopDecision(True, "STOP_LOSS", hwm)

        if self.config.trail_pct > 0:
            activation_price = entry_price * (Decimal("1") + self.config.trail_activation_pct / Decimal("100"))
            if hwm >= activation_price:
                trailing_stop_price = hwm * (Decimal("1") - self.config.trail_pct / Decimal("100"))
                if current_price <= trailing_stop_price:
                    return TrailingStopDecision(True, "TRAILING_STOP", hwm)

        return TrailingStopDecision(False, None, hwm)
