from decimal import Decimal

from aurora.risk.trailing_stop import TrailingStopConfig, TrailingStopEngine


def _engine(**overrides) -> TrailingStopEngine:
    defaults = dict(enabled=True, stop_loss_pct=Decimal("2"), trail_activation_pct=Decimal("3"), trail_pct=Decimal("2"))
    defaults.update(overrides)
    return TrailingStopEngine(TrailingStopConfig(**defaults))


def test_disabled_never_exits_but_still_tracks_high_water():
    engine = _engine(enabled=False)
    decision = engine.evaluate(
        current_price=Decimal("90"), entry_price=Decimal("100"), high_water_price=Decimal("100")
    )
    assert decision.should_exit is False
    assert decision.reason is None
    assert decision.high_water_price == Decimal("100")  # max(100, 90)


def test_hard_stop_loss_fires_below_entry_threshold():
    engine = _engine()
    # entry 100, stop_loss_pct=2 -> stop at 98
    decision = engine.evaluate(
        current_price=Decimal("97"), entry_price=Decimal("100"), high_water_price=Decimal("100")
    )
    assert decision.should_exit is True
    assert decision.reason == "STOP_LOSS"


def test_hard_stop_loss_does_not_fire_above_threshold():
    engine = _engine()
    decision = engine.evaluate(
        current_price=Decimal("99"), entry_price=Decimal("100"), high_water_price=Decimal("100")
    )
    assert decision.should_exit is False


def test_trailing_stop_not_active_before_activation_threshold():
    engine = _engine()
    # up only 2% (activation is 3%) then pulls back - trail never armed,
    # and the pullback itself isn't a stop-loss breach either.
    decision = engine.evaluate(
        current_price=Decimal("100.5"), entry_price=Decimal("100"), high_water_price=Decimal("102")
    )
    assert decision.should_exit is False


def test_trailing_stop_fires_after_activation_and_pullback():
    engine = _engine()
    # Position ran up to 110 (10% - well past the 3% activation), then pulls
    # back 2% off that high-water mark -> exit at 107.8, locking in most of
    # the move instead of waiting for it to erase the whole gain.
    decision = engine.evaluate(
        current_price=Decimal("107.8"), entry_price=Decimal("100"), high_water_price=Decimal("110")
    )
    assert decision.should_exit is True
    assert decision.reason == "TRAILING_STOP"


def test_trailing_stop_keeps_riding_while_still_making_new_highs():
    engine = _engine()
    decision = engine.evaluate(
        current_price=Decimal("111"), entry_price=Decimal("100"), high_water_price=Decimal("110")
    )
    assert decision.should_exit is False
    assert decision.high_water_price == Decimal("111")  # new high recorded


def test_high_water_seeds_from_entry_price_on_first_tick():
    engine = _engine()
    decision = engine.evaluate(current_price=Decimal("101"), entry_price=Decimal("100"), high_water_price=None)
    assert decision.high_water_price == Decimal("101")


def test_stop_loss_pct_zero_disables_hard_stop_only():
    engine = _engine(stop_loss_pct=Decimal("0"))
    decision = engine.evaluate(
        current_price=Decimal("80"), entry_price=Decimal("100"), high_water_price=Decimal("100")
    )
    assert decision.should_exit is False  # would have tripped a nonzero stop_loss_pct


def test_trail_pct_zero_disables_trailing_only():
    engine = _engine(stop_loss_pct=Decimal("0"), trail_pct=Decimal("0"))
    decision = engine.evaluate(
        current_price=Decimal("90"), entry_price=Decimal("100"), high_water_price=Decimal("115")
    )
    assert decision.should_exit is False  # would have tripped trailing (90 <= 115*0.98) with trail_pct nonzero


def test_zero_entry_price_never_exits():
    engine = _engine()
    decision = engine.evaluate(current_price=Decimal("1"), entry_price=Decimal("0"), high_water_price=None)
    assert decision.should_exit is False
