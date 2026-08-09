from __future__ import annotations

from decimal import Decimal

import pandas as pd
import requests

_GRANULARITY_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}

BASE_URL = "https://api.exchange.coinbase.com"


class CoinbasePublicMarketData:
    """Reads Coinbase Exchange's public market data endpoints only. No API
    key required. Used instead of Binance because Binance blocks requests
    from US-hosted cloud IPs (including GitHub Actions runners) as a
    restricted jurisdiction under its terms of service; Coinbase is
    US-licensed and serves those IPs normally."""

    def __init__(self):
        self._session = requests.Session()

    def get_klines(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        granularity = _GRANULARITY_SECONDS.get(timeframe)
        if granularity is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        response = self._session.get(
            f"{BASE_URL}/products/{symbol}/candles",
            params={"granularity": granularity},
            timeout=10,
        )
        response.raise_for_status()
        raw = response.json()  # rows: [time, low, high, open, close, volume], newest first

        df = pd.DataFrame(raw, columns=["time", "low", "high", "open", "close", "volume"])
        df = df.sort_values("time").tail(limit).reset_index(drop=True)
        df["open_time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df[["open_time", "open", "high", "low", "close", "volume"]]

    def get_last_price(self, symbol: str) -> Decimal:
        response = self._session.get(f"{BASE_URL}/products/{symbol}/ticker", timeout=10)
        response.raise_for_status()
        return Decimal(response.json()["price"])
