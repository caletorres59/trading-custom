from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from aurora.backtest.engine import DEFAULT_STOP_DISTANCE_PCT, TradeLogEntry
from aurora.broker.base import Order, OrderSide, OrderType
from aurora.broker.paper_broker import PaperSimulatorBroker
from aurora.risk.risk_engine import AccountState, HardRiskEngine, RiskDecisionType, TradeRequest
from aurora.risk.watchdogs import blocking_failure, run_watchdogs
from aurora.strategy.base import Direction, Strategy


@dataclass
class SymbolStats:
    symbol: str
    trades: int = 0
    pnl_contribution: Decimal = Decimal("0")  # exact: cash flow from fills + final mark-to-market


@dataclass
class MultiSymbolBacktestResult:
    symbols: list[str]
    starting_equity: Decimal
    final_equity: Decimal
    days: int
    equity_curve: list[tuple[pd.Timestamp, Decimal]]
    trades: list[TradeLogEntry]
    total_fees: Decimal
    max_drawdown_pct: Decimal
    risk_rejections: int
    emergency_stops: int
    circuit_breaker_flattens: int
    watchdog_blocks: int
    per_symbol: dict[str, SymbolStats] = field(default_factory=dict)

    @property
    def total_return_pct(self) -> Decimal:
        if self.starting_equity == 0:
            return Decimal("0")
        return (self.final_equity - self.starting_equity) / self.starting_equity * Decimal("100")

    @property
    def avg_monthly_return_pct(self) -> Decimal:
        months = Decimal(self.days) / Decimal("30.44")
        if months == 0:
            return Decimal("0")
        return self.total_return_pct / months

    @property
    def sharpe_ratio(self) -> float:
        if len(self.equity_curve) < 3:
            return 0.0
        values = [float(e) for _, e in self.equity_curve]
        returns = [(values[i] / values[i - 1]) - 1 for i in range(1, len(values)) if values[i - 1] > 0]
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(variance)
        if std == 0:
            return 0.0
        return (mean / std) * math.sqrt(365)


class MultiSymbolBacktestEngine:
    """Replays one strategy across several symbols at once, through a single
    shared PaperSimulatorBroker + HardRiskEngine - the same portfolio, the
    same 50% aggregate-exposure budget, the same kill switch. This is what
    the live loop already does (engine/loop.py iterates config.symbols
    against one broker); this mirrors it for backtests, which engine.py
    only ever did one symbol at a time.

    Candle streams are merged on their timestamps and processed in
    chronological order. At each timestamp, every symbol that has a candle
    there is priced, then (in the caller's symbol order, for determinism)
    gets a signal -> risk -> fill pass."""

    def __init__(
        self,
        strategies: dict[str, Strategy],
        risk_engine: HardRiskEngine,
        symbols: list[str],
        starting_equity: Decimal,
        stop_distance_pct: Decimal = DEFAULT_STOP_DISTANCE_PCT,
        allow_short: bool = False,
    ):
        self.strategies = strategies
        self.risk_engine = risk_engine
        self.symbols = symbols
        self.starting_equity = starting_equity
        self.stop_distance_pct = stop_distance_pct
        self.allow_short = allow_short

    def run(self, candles_by_symbol: dict[str, pd.DataFrame]) -> MultiSymbolBacktestResult:
        for symbol in self.symbols:
            if symbol not in candles_by_symbol:
                raise ValueError(f"No candles provided for {symbol}")

        # Per-symbol: the frame, a timestamp -> row-index map for O(1) window
        # lookup, and the strategy's minimum lookback before it can speak.
        frames: dict[str, pd.DataFrame] = {}
        index_of: dict[str, dict[pd.Timestamp, int]] = {}
        min_lookback: dict[str, int] = {}
        for symbol in self.symbols:
            df = candles_by_symbol[symbol].reset_index(drop=True)
            frames[symbol] = df
            index_of[symbol] = {ts: i for i, ts in enumerate(df["open_time"])}
            strategy = self.strategies[symbol]
            min_lookback[symbol] = getattr(strategy, "slow_period", 1) + 1

        timeline = sorted(set().union(*(set(df["open_time"]) for df in frames.values())))
        if len(timeline) < 2:
            raise ValueError("Not enough candles across the provided symbols to run a backtest")

        clock_box = {"now": timeline[0].to_pydatetime()}
        state = {
            "cash": self.starting_equity,
            "peak_equity": self.starting_equity,
            "equity_at_day_start": self.starting_equity,
            "state_day": clock_box["now"].date().isoformat(),
            "trades_today": 0,
            "positions": {},
        }
        broker = PaperSimulatorBroker(state=state, clock=lambda: clock_box["now"])

        trades: list[TradeLogEntry] = []
        equity_curve: list[tuple[pd.Timestamp, Decimal]] = []
        per_symbol = {s: SymbolStats(symbol=s) for s in self.symbols}
        total_fees = Decimal("0")
        risk_rejections = 0
        emergency_stops = 0
        circuit_breaker_flattens = 0
        watchdog_blocks = 0
        max_dd = Decimal("0")
        last_recorded_day = None
        last_price: dict[str, Decimal] = {}

        def record_fill(symbol: str, side: OrderSide, qty: Decimal, price: Decimal) -> Decimal:
            notional = qty * price
            fee = notional * Decimal("0.001")
            # Exact P&L attribution: SELL adds cash, BUY removes it; the final
            # mark-to-market of any leftover position is added at the end.
            if side == OrderSide.SELL:
                per_symbol[symbol].pnl_contribution += notional - fee
            else:
                per_symbol[symbol].pnl_contribution -= notional + fee
            return fee

        for ts in timeline:
            clock_box["now"] = ts.to_pydatetime()
            active = [s for s in self.symbols if ts in index_of[s]]
            for symbol in active:
                idx = index_of[symbol][ts]
                price = Decimal(str(frames[symbol].iloc[idx]["close"]))
                last_price[symbol] = price
                broker.update_price(symbol, price)

            account = broker.get_account()
            if account.peak_equity > 0:
                tick_dd = (account.peak_equity - account.equity) / account.peak_equity * Decimal("100")
                max_dd = max(max_dd, tick_dd)

            kill_switch = self.risk_engine.check_kill_switch(AccountState(
                equity=account.equity,
                equity_at_day_start=account.equity - account.daily_pnl,
                peak_equity=account.peak_equity,
                daily_pnl=account.daily_pnl,
                current_exposure_pct=Decimal("0"),
                trades_today=account.trades_today,
            ))
            if kill_switch is not None:
                for position in broker.get_positions():
                    if position.quantity == 0:
                        continue
                    side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
                    order = Order(
                        symbol=position.symbol,
                        side=side,
                        order_type=OrderType.MARKET,
                        quantity=abs(position.quantity),
                    )
                    result = broker.submit(order)
                    total_fees += record_fill(
                        position.symbol, side, result.filled_quantity, result.average_fill_price or Decimal("0")
                    )
                    circuit_breaker_flattens += 1
                    per_symbol[position.symbol].trades += 1
                    trades.append(TradeLogEntry(
                        time=ts,
                        direction="FLATTEN",
                        side=side.value,
                        quantity=result.filled_quantity,
                        price=result.average_fill_price or Decimal("0"),
                        confidence=0.0,
                        risk_decision=kill_switch.decision.value,
                        symbol=position.symbol,
                    ))
                broker.reset_drawdown_baseline()

            for symbol in active:
                idx = index_of[symbol][ts]
                if idx < min_lookback[symbol]:
                    continue
                window = frames[symbol].iloc[: idx + 1]
                signal = self.strategies[symbol].generate_signal(symbol, window)
                if signal.direction == Direction.NO_TRADE:
                    continue

                account = broker.get_account()
                positions = broker.get_positions()
                exposure_notional = sum(
                    (p.quantity * p.average_entry_price for p in positions), Decimal("0")
                )
                exposure_pct = (
                    (exposure_notional / account.equity * Decimal("100")) if account.equity else Decimal("0")
                )
                position_quantity = next(
                    (p.quantity for p in positions if p.symbol == symbol), Decimal("0")
                )
                account_state = AccountState(
                    equity=account.equity,
                    equity_at_day_start=account.equity - account.daily_pnl,
                    peak_equity=account.peak_equity,
                    daily_pnl=account.daily_pnl,
                    current_exposure_pct=exposure_pct,
                    trades_today=account.trades_today,
                )
                trade_request = TradeRequest(
                    symbol=symbol,
                    direction=signal.direction.value,
                    stop_distance_pct=self.stop_distance_pct,
                    position_quantity=position_quantity,
                )
                risk_decision = self.risk_engine.evaluate(trade_request, account_state)

                if risk_decision.decision == RiskDecisionType.EMERGENCY_STOP:
                    emergency_stops += 1
                    continue
                if risk_decision.decision == RiskDecisionType.REJECT:
                    risk_rejections += 1
                    continue
                if risk_decision.decision not in (RiskDecisionType.APPROVE, RiskDecisionType.REDUCE):
                    continue

                current_price = last_price[symbol]
                positions_notional = sum(
                    (
                        p.quantity * (last_price.get(p.symbol) or p.average_entry_price)
                        for p in positions
                    ),
                    Decimal("0"),
                )
                watchdog_reports = run_watchdogs(
                    candles=window,
                    reported_equity=account.equity,
                    cash=account.available_balance,
                    positions_notional=positions_notional,
                )
                if blocking_failure(watchdog_reports) is not None:
                    watchdog_blocks += 1
                    continue

                quantity = (risk_decision.approved_notional / current_price).quantize(Decimal("0.00000001"))
                side = OrderSide.BUY if signal.direction == Direction.LONG else OrderSide.SELL
                if not self.allow_short and side == OrderSide.SELL and quantity > position_quantity:
                    quantity = max(position_quantity, Decimal("0"))
                if quantity <= 0:
                    continue

                order = Order(symbol=symbol, side=side, order_type=OrderType.MARKET, quantity=quantity)
                result = broker.submit(order)
                total_fees += record_fill(
                    symbol, side, result.filled_quantity, result.average_fill_price or Decimal("0")
                )
                per_symbol[symbol].trades += 1
                trades.append(TradeLogEntry(
                    time=ts,
                    direction=signal.direction.value,
                    side=side.value,
                    quantity=result.filled_quantity,
                    price=result.average_fill_price or Decimal("0"),
                    confidence=signal.confidence,
                    risk_decision=risk_decision.decision.value,
                    symbol=symbol,
                ))

            current_day = ts.date()
            if current_day != last_recorded_day:
                last_recorded_day = current_day
                equity_curve.append((ts, broker.get_account().equity))

        # Add the final mark-to-market of any position left open, so each
        # symbol's pnl_contribution sums exactly to (final_equity - start).
        for position in broker.get_positions():
            if position.symbol in per_symbol:
                per_symbol[position.symbol].pnl_contribution += (
                    position.quantity * (last_price.get(position.symbol) or position.average_entry_price)
                )

        final_account = broker.get_account()
        return MultiSymbolBacktestResult(
            symbols=list(self.symbols),
            starting_equity=self.starting_equity,
            final_equity=final_account.equity,
            days=(timeline[-1] - timeline[0]).days,
            equity_curve=equity_curve,
            trades=trades,
            total_fees=total_fees,
            max_drawdown_pct=max_dd,
            risk_rejections=risk_rejections,
            emergency_stops=emergency_stops,
            circuit_breaker_flattens=circuit_breaker_flattens,
            watchdog_blocks=watchdog_blocks,
            per_symbol=per_symbol,
        )
