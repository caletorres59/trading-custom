from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from aurora.broker.base import Order, OrderSide, OrderType
from aurora.broker.paper_broker import PaperSimulatorBroker
from aurora.risk.risk_engine import AccountState, HardRiskEngine, RiskDecisionType, TradeRequest
from aurora.risk.watchdogs import blocking_failure, run_watchdogs
from aurora.strategy.base import Direction, Strategy

DEFAULT_STOP_DISTANCE_PCT = Decimal("1.0")  # matches the live loop's placeholder


@dataclass
class TradeLogEntry:
    time: pd.Timestamp
    direction: str
    side: str
    quantity: Decimal
    price: Decimal
    confidence: float
    risk_decision: str


@dataclass
class BacktestResult:
    symbol: str
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
    watchdog_blocks: int = 0

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
        # equity_curve is sampled once per day, so annualize with 365 periods/year
        return (mean / std) * math.sqrt(365)


class BacktestEngine:
    """Replays a strategy against historical candles through the same
    Strategy -> HardRiskEngine -> PaperSimulatorBroker pipeline the live
    loop uses, so a backtest result reflects what the live system would
    actually have done - not a separate, idealized simulation."""

    def __init__(
        self,
        strategy: Strategy,
        risk_engine: HardRiskEngine,
        symbol: str,
        starting_equity: Decimal,
        stop_distance_pct: Decimal = DEFAULT_STOP_DISTANCE_PCT,
    ):
        self.strategy = strategy
        self.risk_engine = risk_engine
        self.symbol = symbol
        self.starting_equity = starting_equity
        self.stop_distance_pct = stop_distance_pct

    def run(self, candles: pd.DataFrame) -> BacktestResult:
        min_lookback = getattr(self.strategy, "slow_period", 1) + 1
        if len(candles) <= min_lookback:
            raise ValueError("Not enough candles to run a backtest with this strategy's lookback")

        clock_box = {"now": candles["open_time"].iloc[0].to_pydatetime()}
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
        total_fees = Decimal("0")
        risk_rejections = 0
        emergency_stops = 0
        circuit_breaker_flattens = 0
        watchdog_blocks = 0
        last_recorded_day = None

        for i in range(min_lookback, len(candles)):
            window = candles.iloc[: i + 1]
            row = candles.iloc[i]
            clock_box["now"] = row["open_time"].to_pydatetime()
            last_price = Decimal(str(row["close"]))
            broker.update_price(self.symbol, last_price)

            account = broker.get_account()
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
                    order = Order(symbol=self.symbol, side=side, order_type=OrderType.MARKET, quantity=abs(position.quantity))
                    result = broker.submit(order)
                    fee = result.filled_quantity * (result.average_fill_price or Decimal("0")) * Decimal("0.001")
                    total_fees += fee
                    circuit_breaker_flattens += 1
                    trades.append(TradeLogEntry(
                        time=row["open_time"],
                        direction="FLATTEN",
                        side=side.value,
                        quantity=result.filled_quantity,
                        price=result.average_fill_price or Decimal("0"),
                        confidence=0.0,
                        risk_decision=kill_switch.decision.value,
                    ))

            signal = self.strategy.generate_signal(self.symbol, window)

            if signal.direction != Direction.NO_TRADE:
                account = broker.get_account()
                positions = broker.get_positions()
                exposure_notional = sum(
                    (p.quantity * p.average_entry_price for p in positions), Decimal("0")
                )
                exposure_pct = (
                    (exposure_notional / account.equity * Decimal("100")) if account.equity else Decimal("0")
                )
                position_quantity = next(
                    (p.quantity for p in positions if p.symbol == self.symbol), Decimal("0")
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
                    symbol=self.symbol,
                    direction=signal.direction.value,
                    stop_distance_pct=self.stop_distance_pct,
                    position_quantity=position_quantity,
                )
                risk_decision = self.risk_engine.evaluate(trade_request, account_state)

                if risk_decision.decision == RiskDecisionType.EMERGENCY_STOP:
                    emergency_stops += 1
                elif risk_decision.decision == RiskDecisionType.REJECT:
                    risk_rejections += 1
                elif risk_decision.decision in (RiskDecisionType.APPROVE, RiskDecisionType.REDUCE):
                    positions_notional = sum(
                        (p.quantity * (last_price if p.symbol == self.symbol else p.average_entry_price) for p in positions),
                        Decimal("0"),
                    )
                    watchdog_reports = run_watchdogs(
                        candles=window,
                        reported_equity=account.equity,
                        cash=account.available_balance,
                        positions_notional=positions_notional,
                    )
                    quantity = Decimal("0")
                    if blocking_failure(watchdog_reports) is not None:
                        watchdog_blocks += 1
                    else:
                        quantity = (risk_decision.approved_notional / last_price).quantize(Decimal("0.00000001"))
                    if quantity > 0:
                        side = OrderSide.BUY if signal.direction == Direction.LONG else OrderSide.SELL
                        order = Order(symbol=self.symbol, side=side, order_type=OrderType.MARKET, quantity=quantity)
                        result = broker.submit(order)
                        fee = result.filled_quantity * (result.average_fill_price or Decimal("0")) * Decimal("0.001")
                        total_fees += fee
                        trades.append(TradeLogEntry(
                            time=row["open_time"],
                            direction=signal.direction.value,
                            side=side.value,
                            quantity=result.filled_quantity,
                            price=result.average_fill_price or Decimal("0"),
                            confidence=signal.confidence,
                            risk_decision=risk_decision.decision.value,
                        ))

            current_day = row["open_time"].date()
            if current_day != last_recorded_day:
                last_recorded_day = current_day
                equity_curve.append((row["open_time"], broker.get_account().equity))

        final_account = broker.get_account()
        peak = self.starting_equity
        max_dd = Decimal("0")
        for _, equity in equity_curve:
            peak = max(peak, equity)
            if peak > 0:
                dd = (peak - equity) / peak * Decimal("100")
                max_dd = max(max_dd, dd)

        return BacktestResult(
            symbol=self.symbol,
            starting_equity=self.starting_equity,
            final_equity=final_account.equity,
            days=(candles["open_time"].iloc[-1] - candles["open_time"].iloc[0]).days,
            equity_curve=equity_curve,
            trades=trades,
            watchdog_blocks=watchdog_blocks,
            total_fees=total_fees,
            max_drawdown_pct=max_dd,
            risk_rejections=risk_rejections,
            emergency_stops=emergency_stops,
            circuit_breaker_flattens=circuit_breaker_flattens,
        )
