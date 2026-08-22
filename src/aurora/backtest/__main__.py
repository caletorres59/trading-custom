from __future__ import annotations

import argparse
import logging

from aurora.backtest.data_loader import CoinbaseHistoricalLoader
from aurora.backtest.engine import BacktestEngine
from aurora.config import AppConfig, load_config
from aurora.risk.risk_engine import HardRiskEngine
from aurora.strategy.breakout import BreakoutStrategy
from aurora.strategy.sma_crossover import SmaCrossoverStrategy
from aurora.strategy.volatility_spike import VolatilitySpikeStrategy

STRATEGIES = {
    "sma_crossover": SmaCrossoverStrategy,
    "breakout": BreakoutStrategy,
    "volatility_spike": VolatilitySpikeStrategy,
}


def build_strategy(config: AppConfig):
    strategy_cls = STRATEGIES[config.strategy.name]
    return strategy_cls(**config.strategy.params)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Backtest the configured strategy against Coinbase history")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--days", type=int, default=90, help="How many days of history to test against")
    args = parser.parse_args()

    config = load_config(args.config)
    symbol = config.symbols[0]

    loader = CoinbaseHistoricalLoader()
    candles = loader.load(symbol, config.timeframe, args.days)

    strategy = build_strategy(config)
    risk_engine = HardRiskEngine(config.risk)
    engine = BacktestEngine(
        strategy=strategy,
        risk_engine=risk_engine,
        symbol=symbol,
        starting_equity=config.starting_equity,
    )
    result = engine.run(candles)

    print()
    print("=" * 60)
    print(f"BACKTEST: {strategy.name} on {symbol} ({config.timeframe}) — {result.days} days")
    print("=" * 60)
    print(f"Starting equity:       ${result.starting_equity:,.2f}")
    print(f"Final equity:          ${result.final_equity:,.2f}")
    print(f"Total return:          {result.total_return_pct:+.2f}%")
    print(f"Avg monthly return:    {result.avg_monthly_return_pct:+.2f}%")
    print(f"Max drawdown:          {result.max_drawdown_pct:.2f}%")
    print(f"Sharpe ratio (approx): {result.sharpe_ratio:.2f}")
    print(f"Total trades executed: {len(result.trades)}")
    print(f"Risk rejections:       {result.risk_rejections}")
    print(f"Emergency stops:       {result.emergency_stops}")
    print(f"Watchdog blocks:       {result.watchdog_blocks}")
    print(f"Circuit breaker flattens: {result.circuit_breaker_flattens}")
    print(f"Total fees paid:       ${result.total_fees:,.2f}")
    print("=" * 60)

    if result.trades:
        print("\nTrade log:")
        for t in result.trades:
            print(f"  {t.time} {t.side:4s} {t.quantity} @ ${t.price} (conf={t.confidence:.2f}, {t.risk_decision})")
    print()


if __name__ == "__main__":
    main()
