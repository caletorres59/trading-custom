from __future__ import annotations

import argparse
import logging

from dotenv import load_dotenv

from aurora.broker.paper_broker import PaperSimulatorBroker
from aurora.config import AppConfig, load_config
from aurora.db.portfolio_store import load_portfolio_state
from aurora.db.session import init_db
from aurora.engine.loop import TradingLoop
from aurora.market_data.binance_provider import BinancePublicMarketData
from aurora.risk.risk_engine import HardRiskEngine
from aurora.strategy.sma_crossover import SmaCrossoverStrategy

STRATEGIES = {
    "sma_crossover": SmaCrossoverStrategy,
}


def build_strategy(config: AppConfig):
    strategy_cls = STRATEGIES[config.strategy.name]
    return strategy_cls(**config.strategy.params)


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Aurora trading loop (paper mode MVP)")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--once", action="store_true", help="Run a single iteration and exit")
    args = parser.parse_args()

    config = load_config(args.config)
    session_factory = init_db(config.database_url)

    portfolio_state = load_portfolio_state(session_factory, config.starting_equity)
    broker = PaperSimulatorBroker(state=portfolio_state)
    market_data = BinancePublicMarketData()
    strategy = build_strategy(config)
    risk_engine = HardRiskEngine(config.risk)

    loop = TradingLoop(config, market_data, broker, strategy, risk_engine, session_factory)

    if args.once:
        loop.run_once()
    else:
        loop.run_forever()


if __name__ == "__main__":
    main()
