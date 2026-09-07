from decimal import Decimal

import pandas as pd

from aurora.broker.alpaca_broker import AlpacaBroker
from aurora.config import AppConfig, RiskLimits, StrategyConfig
from aurora.db.models import AuditEvent, OrderRecord
from aurora.db.session import init_db, session_scope
from aurora.engine.loop import TradingLoop
from aurora.risk.risk_engine import HardRiskEngine
from aurora.strategy.base import Direction, Signal, Strategy
from tests.test_alpaca_broker import FakeSession, bookkeeping


class StubMarketData:
    def __init__(self, closes):
        self._closes = closes

    def get_klines(self, symbol, timeframe, limit=200):
        n = len(self._closes)
        return pd.DataFrame({
            "open_time": pd.date_range("2026-09-01", periods=n, freq="5min", tz="UTC"),
            "open": self._closes,
            "high": self._closes,
            "low": self._closes,
            "close": self._closes,
            "volume": [1.0] * n,
        })


class ForcedStrategy(Strategy):
    name = "forced"

    def __init__(self, direction):
        self.direction = direction

    def generate_signal(self, symbol, candles):
        return Signal(symbol, self.direction, 0.9, ["FORCED"])


def make_config(**overrides):
    risk = RiskLimits(
        max_daily_loss_pct=Decimal("15"),
        max_trade_risk_pct=Decimal("0.5"),
        max_position_pct=Decimal("10"),
        max_portfolio_exposure_pct=Decimal("50"),
        max_drawdown_pct=Decimal("30"),
        max_leverage=Decimal("1"),
        max_trades_per_day=30,
    )
    defaults = dict(
        mode="PAPER",
        symbols=["BTC-USD"],
        timeframe="5m",
        strategy=StrategyConfig(name="forced", params={}),
        risk=risk,
        loop_interval_seconds=60,
        starting_equity=Decimal("100000"),
        database_url="sqlite://",
        allow_short=False,
        alpaca_api_key_id="k",
        alpaca_api_secret_key="s",
        alpaca_base_url="https://paper-api.alpaca.markets",
    )
    defaults.update(overrides)
    return AppConfig(**defaults)


def build_loop(direction, session, closes, *, config=None):
    config = config or make_config()
    sf = init_db("sqlite://")
    broker = AlpacaBroker("k", "s", "https://paper-api.alpaca.markets",
                          bookkeeping(), needs_seed=False, session=session)
    loop = TradingLoop(config, StubMarketData(closes), broker,
                       ForcedStrategy(direction), HardRiskEngine(config.risk), sf)
    return loop, sf


def test_long_signal_places_a_buy_order():
    session = FakeSession()
    session.next_fill = ("0.12", "79000")
    loop, sf = build_loop(Direction.LONG, session, [100] * 25)

    loop.run_once()

    with session_scope(sf) as s:
        orders = s.query(OrderRecord).all()
        assert len(orders) == 1
        assert orders[0].side == "BUY"
        assert orders[0].status == "FILLED"


def test_short_signal_with_no_long_is_skipped_and_audited():
    session = FakeSession()  # no positions held
    loop, sf = build_loop(Direction.SHORT, session, [100] * 25)

    loop.run_once()

    posts = [c for c in session.log if c[0] == "POST"]
    assert posts == []  # never hit Alpaca with a naked short

    with session_scope(sf) as s:
        assert s.query(OrderRecord).count() == 0
        events = [e.event_type for e in s.query(AuditEvent).all()]
        assert "SHORT_SKIPPED_SPOT_LONG_ONLY" in events


def test_short_signal_reduces_an_existing_long():
    session = FakeSession()
    session.positions = [{"symbol": "BTCUSD", "qty": "0.05", "avg_entry_price": "79000"}]
    session.next_fill = ("0.05", "79000")
    loop, sf = build_loop(Direction.SHORT, session, [100] * 25)

    loop.run_once()

    posts = [c for c in session.log if c[0] == "POST"]
    assert len(posts) == 1
    body = posts[0][3]
    assert body["side"] == "sell"
    assert Decimal(body["qty"]) <= Decimal("0.05")  # never sells more than held


def test_allow_short_true_lets_a_naked_short_through():
    session = FakeSession()
    session.next_fill = ("0.12", "79000")
    loop, sf = build_loop(Direction.SHORT, session, [100] * 25, config=make_config(allow_short=True))

    loop.run_once()

    posts = [c for c in session.log if c[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][3]["side"] == "sell"
