from __future__ import annotations

from decimal import Decimal

import pandas as pd
from binance.client import Client

_INTERVAL_MAP = {
    "1m": Client.KLINE_INTERVAL_1MINUTE,
    "5m": Client.KLINE_INTERVAL_5MINUTE,
    "15m": Client.KLINE_INTERVAL_15MINUTE,
    "1h": Client.KLINE_INTERVAL_1HOUR,
    "4h": Client.KLINE_INTERVAL_4HOUR,
    "1d": Client.KLINE_INTERVAL_1DAY,
}


class BinancePublicMarketData:
    """Reads Binance's public market data endpoints only. No API key
    required — this never touches an account or places orders."""

    def __init__(self):
        self._client = Client()

    def get_klines(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        interval = _INTERVAL_MAP.get(timeframe)
        if interval is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        raw = self._client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(
            raw,
            columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades",
                "taker_buy_base", "taker_buy_quote", "ignore",
            ],
        )
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        return df[["open_time", "open", "high", "low", "close", "volume"]]

    def get_last_price(self, symbol: str) -> Decimal:
        ticker = self._client.get_symbol_ticker(symbol=symbol)
        return Decimal(ticker["price"])
