from __future__ import annotations

import json
import logging
import time
import uuid
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from aurora.broker.base import Order, OrderSide, OrderType, TradingBroker
from aurora.broker.paper_broker import PaperSimulatorBroker
from aurora.config import AppConfig
from aurora.db.models import AuditEvent, EquitySnapshot, OrderRecord, RiskDecisionRecord, SignalRecord
from aurora.db.portfolio_store import save_portfolio_state
from aurora.db.session import session_scope
from aurora.market_data.coinbase_provider import CoinbasePublicMarketData
from aurora.risk.risk_engine import AccountState, HardRiskEngine, RiskDecisionType, TradeRequest
from aurora.risk.watchdogs import blocking_failure, run_watchdogs
from aurora.strategy.base import Direction, Strategy

logger = logging.getLogger("aurora.engine")

DEFAULT_STOP_DISTANCE_PCT = Decimal("1.0")  # placeholder until an ATR-based stop is wired in


class TradingLoop:
    """Wires market data -> strategy -> risk engine -> broker -> audit
    trail, per symbol, per spec.md's mandatory one-way pipeline (section
    2, Regla 1). Every iteration gets a correlation_id so a signal, its
    risk decision, and the resulting order can be traced back together."""

    def __init__(
        self,
        config: AppConfig,
        market_data: CoinbasePublicMarketData,
        broker: TradingBroker,
        strategy: Strategy,
        risk_engine: HardRiskEngine,
        session_factory: sessionmaker,
    ):
        self.config = config
        self.market_data = market_data
        self.broker = broker
        self.strategy = strategy
        self.risk_engine = risk_engine
        self.session_factory = session_factory

    def run_once(self) -> None:
        for symbol in self.config.symbols:
            self._process_symbol(symbol)
        if isinstance(self.broker, PaperSimulatorBroker):
            save_portfolio_state(self.session_factory, self.broker.export_state())
            self._record_equity_snapshot()

    def _record_equity_snapshot(self) -> None:
        account = self.broker.get_account()
        drawdown_pct = (
            (account.peak_equity - account.equity) / account.peak_equity * Decimal("100")
            if account.peak_equity
            else Decimal("0")
        )
        with session_scope(self.session_factory) as session:
            session.add(EquitySnapshot(
                equity=account.equity,
                cash=account.available_balance,
                peak_equity=account.peak_equity,
                drawdown_pct=drawdown_pct,
                daily_pnl=account.daily_pnl,
            ))

    def run_forever(self) -> None:
        while True:
            self.run_once()
            time.sleep(self.config.loop_interval_seconds)

    def _enforce_kill_switch(self, symbol: str, correlation_id: str) -> None:
        """Runs every tick, independent of whether the strategy emits a
        signal, so a losing open position gets flattened as soon as it
        breaches the daily-loss or max-drawdown limit - not only whenever
        the strategy next happens to speak up (see risk_engine.check_kill_switch)."""
        account = self.broker.get_account()
        account_state = AccountState(
            equity=account.equity,
            equity_at_day_start=account.equity - account.daily_pnl,
            peak_equity=account.peak_equity,
            daily_pnl=account.daily_pnl,
            current_exposure_pct=Decimal("0"),
            trades_today=account.trades_today,
        )
        decision = self.risk_engine.check_kill_switch(account_state)
        if decision is None:
            return

        for position in self.broker.get_positions():
            if position.symbol != symbol or position.quantity == 0:
                continue
            side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
            order = Order(symbol=symbol, side=side, order_type=OrderType.MARKET, quantity=abs(position.quantity))
            result = self.broker.submit(order)
            logger.warning(
                "circuit_breaker_flatten symbol=%s side=%s quantity=%s reasons=%s",
                symbol, side.value, result.filled_quantity, decision.reasons,
            )
            with session_scope(self.session_factory) as session:
                session.add(OrderRecord(
                    correlation_id=correlation_id,
                    broker_order_id=result.broker_order_id,
                    symbol=symbol,
                    side=side.value,
                    quantity=result.filled_quantity,
                    fill_price=result.average_fill_price or Decimal("0"),
                    status=result.status.value,
                ))
                session.add(RiskDecisionRecord(
                    correlation_id=correlation_id,
                    decision=decision.decision.value,
                    approved_notional=Decimal("0"),
                    reasons=json.dumps(decision.reasons),
                ))
                session.add(AuditEvent(
                    correlation_id=correlation_id,
                    event_type="CIRCUIT_BREAKER_FLATTEN",
                    payload=json.dumps({
                        "symbol": symbol,
                        "quantity": str(result.filled_quantity),
                        "price": str(result.average_fill_price),
                        "reasons": decision.reasons,
                    }),
                ))

        if isinstance(self.broker, PaperSimulatorBroker):
            self.broker.reset_drawdown_baseline()

    def _process_symbol(self, symbol: str) -> None:
        correlation_id = str(uuid.uuid4())
        candles = self.market_data.get_klines(symbol, self.config.timeframe)
        last_price = Decimal(str(candles["close"].iloc[-1]))

        if isinstance(self.broker, PaperSimulatorBroker):
            self.broker.update_price(symbol, last_price)

        self._enforce_kill_switch(symbol, correlation_id)

        signal = self.strategy.generate_signal(symbol, candles)
        logger.info(
            "signal symbol=%s direction=%s confidence=%.2f",
            symbol, signal.direction.value, signal.confidence,
        )

        with session_scope(self.session_factory) as session:
            session.add(SignalRecord(
                correlation_id=correlation_id,
                symbol=symbol,
                strategy=self.strategy.name,
                direction=signal.direction.value,
                confidence=signal.confidence,
                reason_codes=json.dumps(signal.reason_codes),
            ))

        if signal.direction == Direction.NO_TRADE:
            return

        account = self.broker.get_account()
        positions = self.broker.get_positions()
        exposure_notional = sum((p.quantity * p.average_entry_price for p in positions), Decimal("0"))
        exposure_pct = (exposure_notional / account.equity * Decimal("100")) if account.equity else Decimal("0")
        position_quantity = next((p.quantity for p in positions if p.symbol == symbol), Decimal("0"))

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
            stop_distance_pct=DEFAULT_STOP_DISTANCE_PCT,
            position_quantity=position_quantity,
        )

        risk_decision = self.risk_engine.evaluate(trade_request, account_state)
        logger.info(
            "risk_decision symbol=%s decision=%s reasons=%s",
            symbol, risk_decision.decision.value, risk_decision.reasons,
        )

        with session_scope(self.session_factory) as session:
            session.add(RiskDecisionRecord(
                correlation_id=correlation_id,
                decision=risk_decision.decision.value,
                approved_notional=risk_decision.approved_notional,
                reasons=json.dumps(risk_decision.reasons),
            ))

        if risk_decision.decision not in (RiskDecisionType.APPROVE, RiskDecisionType.REDUCE):
            return

        positions_notional = sum(
            (p.quantity * (last_price if p.symbol == symbol else p.average_entry_price) for p in positions),
            Decimal("0"),
        )
        watchdog_reports = run_watchdogs(
            candles=candles,
            reported_equity=account.equity,
            cash=account.available_balance,
            positions_notional=positions_notional,
        )
        with session_scope(self.session_factory) as session:
            for report in watchdog_reports:
                session.add(AuditEvent(
                    correlation_id=correlation_id,
                    event_type="WATCHDOG_CHECK",
                    payload=json.dumps({
                        "name": report.name,
                        "passed": report.passed,
                        "blocking": report.blocking,
                        "reason": report.reason,
                    }),
                ))

        blocker = blocking_failure(watchdog_reports)
        if blocker is not None:
            logger.warning("watchdog_blocked symbol=%s name=%s reason=%s", symbol, blocker.name, blocker.reason)
            with session_scope(self.session_factory) as session:
                session.add(AuditEvent(
                    correlation_id=correlation_id,
                    event_type="WATCHDOG_BLOCKED",
                    payload=json.dumps({"symbol": symbol, "name": blocker.name, "reason": blocker.reason}),
                ))
            return

        quantity = (risk_decision.approved_notional / last_price).quantize(Decimal("0.00000001"))
        if quantity <= 0:
            return

        side = OrderSide.BUY if signal.direction == Direction.LONG else OrderSide.SELL
        order = Order(symbol=symbol, side=side, order_type=OrderType.MARKET, quantity=quantity)
        result = self.broker.submit(order)

        with session_scope(self.session_factory) as session:
            session.add(OrderRecord(
                correlation_id=correlation_id,
                broker_order_id=result.broker_order_id,
                symbol=symbol,
                side=side.value,
                quantity=result.filled_quantity,
                fill_price=result.average_fill_price or Decimal("0"),
                status=result.status.value,
            ))
            session.add(AuditEvent(
                correlation_id=correlation_id,
                event_type="TRADE_EXECUTED",
                payload=json.dumps({
                    "symbol": symbol,
                    "direction": signal.direction.value,
                    "confidence": signal.confidence,
                    "risk_decision": risk_decision.decision.value,
                    "quantity": str(result.filled_quantity),
                    "price": str(result.average_fill_price),
                }),
            ))
