from __future__ import annotations

import argparse
import logging

from aurora.backtest.data_loader import CoinbaseHistoricalLoader
from aurora.backtest.engine import BacktestEngine
from aurora.backtest.multi_engine import MultiSymbolBacktestEngine
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


def _run_single(config: AppConfig, symbol: str, days: int) -> None:
    loader = CoinbaseHistoricalLoader()
    candles = loader.load(symbol, config.timeframe, days)

    strategy = build_strategy(config)
    engine = BacktestEngine(
        strategy=strategy,
        risk_engine=HardRiskEngine(config.risk),
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


def _run_multi(config: AppConfig, symbols: list[str], days: int) -> None:
    loader = CoinbaseHistoricalLoader()
    candles_by_symbol = {s: loader.load(s, config.timeframe, days) for s in symbols}

    strategies = {s: build_strategy(config) for s in symbols}
    engine = MultiSymbolBacktestEngine(
        strategies=strategies,
        risk_engine=HardRiskEngine(config.risk),
        symbols=symbols,
        starting_equity=config.starting_equity,
    )
    result = engine.run(candles_by_symbol)

    name = config.strategy.name
    print()
    print("=" * 60)
    print(f"BACKTEST (basket): {name} on {', '.join(symbols)} ({config.timeframe}) — {result.days} days")
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
    print("-" * 60)
    print("Per-symbol contribution to total P&L (exact, sums to total):")
    for symbol in symbols:
        stats = result.per_symbol[symbol]
        print(f"  {symbol:10s} {stats.trades:4d} trades   ${stats.pnl_contribution:+,.2f}")
    print("=" * 60)
    print()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Backtest the configured strategy against Coinbase history")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--days", type=int, default=90, help="How many days of history to test against")
    parser.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated symbol override (e.g. BTC-USD,ETH-USD,SOL-USD). "
        "Defaults to config.symbols. More than one runs the shared-portfolio basket backtest.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else list(config.symbols)

    if len(symbols) == 1:
        _run_single(config, symbols[0], args.days)
    else:
        _run_multi(config, symbols, args.days)


if __name__ == "__main__":
    main()
