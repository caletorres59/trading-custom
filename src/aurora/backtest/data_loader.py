from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

logger = logging.getLogger("aurora.backtest.data_loader")

BASE_URL = "https://api.exchange.coinbase.com"

_GRANULARITY_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}

MAX_CANDLES_PER_REQUEST = 300


class CoinbaseHistoricalLoader:
    """Fetches historical candles beyond what a single Coinbase request can
    return (capped at 300 candles) by paging backward through time."""

    def __init__(self, request_delay_seconds: float = 0.35):
        self._session = requests.Session()
        self._request_delay_seconds = request_delay_seconds

    def load(self, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
        granularity = _GRANULARITY_SECONDS.get(timeframe)
        if granularity is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        chunk_span = timedelta(seconds=granularity * MAX_CANDLES_PER_REQUEST)
        range_end = datetime.now(timezone.utc)
        range_start = range_end - timedelta(days=days)

        all_rows: list[list] = []
        chunk_end = range_end
        while chunk_end > range_start:
            chunk_start = max(range_start, chunk_end - chunk_span)
            rows = self._fetch_chunk(symbol, granularity, chunk_start, chunk_end)
            all_rows.extend(rows)
            chunk_end = chunk_start
            time.sleep(self._request_delay_seconds)

        if not all_rows:
            raise RuntimeError(f"No historical data returned for {symbol} {timeframe} over {days}d")

        df = pd.DataFrame(all_rows, columns=["time", "low", "high", "open", "close", "volume"])
        df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
        df["open_time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        logger.info("loaded %d candles for %s %s over %dd", len(df), symbol, timeframe, days)
        return df[["open_time", "open", "high", "low", "close", "volume"]]

    def _fetch_chunk(self, symbol: str, granularity: int, start: datetime, end: datetime) -> list[list]:
        for attempt in range(3):
            response = self._session.get(
                f"{BASE_URL}/products/{symbol}/candles",
                params={
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "granularity": granularity,
                },
                timeout=15,
            )
            if response.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(f"Rate limited fetching {symbol} candles after 3 attempts")
