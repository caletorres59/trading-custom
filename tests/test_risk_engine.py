from decimal import Decimal

from aurora.config import RiskLimits
from aurora.risk.risk_engine import AccountState, HardRiskEngine, RiskDecisionType, TradeRequest


def make_limits(**overrides):
    defaults = dict(
        max_daily_loss_pct=Decimal("0.5"),
        max_trade_risk_pct=Decimal("0.10"),
        max_position_pct=Decimal("1.0"),
        max_portfolio_exposure_pct=Decimal("5.0"),
        max_drawdown_pct=Decimal("8.0"),
        max_leverage=Decimal("1.0"),
        max_trades_per_day=10,
    )
    defaults.update(overrides)
    return RiskLimits(**defaults)


def make_account(**overrides):
    defaults = dict(
        equity=Decimal("1000"),
        equity_at_day_start=Decimal("1000"),
        peak_equity=Decimal("1000"),
        daily_pnl=Decimal("0"),
        current_exposure_pct=Decimal("0"),
        trades_today=0,
    )
    defaults.update(overrides)
    return AccountState(**defaults)


def test_approves_when_risk_based_size_is_within_caps():
    engine = HardRiskEngine(make_limits())
    decision = engine.evaluate(
        TradeRequest(symbol="BTCUSDT", direction="LONG", stop_distance_pct=Decimal("20.0")),
        make_account(),
    )
    # risk_budget = 1000 * 0.10% = 1; sized = 1 / 20% = 5; below the 1% position cap (10) and 5% exposure cap (50)
    assert decision.decision == RiskDecisionType.APPROVE
    assert decision.approved_notional == Decimal("5")


def test_reduces_size_when_position_cap_binds():
    engine = HardRiskEngine(make_limits())
    decision = engine.evaluate(
        TradeRequest(symbol="BTCUSDT", direction="LONG", stop_distance_pct=Decimal("1.0")),
        make_account(),
    )
    # risk_budget = 1000 * 0.10% = 1; sized = 1 / 1% = 100; capped by the 1% max position (10)
    assert decision.decision == RiskDecisionType.REDUCE
    assert decision.approved_notional == Decimal("10")


def test_rejects_when_daily_loss_limit_breached():
    engine = HardRiskEngine(make_limits())
    account = make_account(daily_pnl=Decimal("-6"))  # -0.6% > 0.5% limit
    decision = engine.evaluate(
        TradeRequest(symbol="BTCUSDT", direction="LONG", stop_distance_pct=Decimal("1.0")),
        account,
    )
    assert decision.decision == RiskDecisionType.EMERGENCY_STOP
    assert decision.approved_notional == 0


def test_rejects_when_drawdown_limit_breached():
    engine = HardRiskEngine(make_limits())
    account = make_account(equity=Decimal("900"), peak_equity=Decimal("1000"))  # 10% dd > 8% limit
    decision = engine.evaluate(
        TradeRequest(symbol="BTCUSDT", direction="LONG", stop_distance_pct=Decimal("1.0")),
        account,
    )
    assert decision.decision == RiskDecisionType.EMERGENCY_STOP


def test_rejects_when_max_trades_reached():
    engine = HardRiskEngine(make_limits(max_trades_per_day=1))
    account = make_account(trades_today=1)
    decision = engine.evaluate(
        TradeRequest(symbol="BTCUSDT", direction="LONG", stop_distance_pct=Decimal("1.0")),
        account,
    )
    assert decision.decision == RiskDecisionType.REJECT
    assert "MAX_TRADES_PER_DAY_REACHED" in decision.reasons


def test_rejects_when_portfolio_exposure_exhausted():
    engine = HardRiskEngine(make_limits())
    account = make_account(current_exposure_pct=Decimal("5.0"))
    decision = engine.evaluate(
        TradeRequest(symbol="BTCUSDT", direction="LONG", stop_distance_pct=Decimal("1.0")),
        account,
    )
    assert decision.decision == RiskDecisionType.REJECT
    assert "MAX_PORTFOLIO_EXPOSURE_REACHED" in decision.reasons


def test_rejects_invalid_stop_distance():
    engine = HardRiskEngine(make_limits())
    decision = engine.evaluate(
        TradeRequest(symbol="BTCUSDT", direction="LONG", stop_distance_pct=Decimal("0")),
        make_account(),
    )
    assert decision.decision == RiskDecisionType.REJECT
    assert "INVALID_STOP_DISTANCE" in decision.reasons
