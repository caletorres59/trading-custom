from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import pandas as pd


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class Signal:
    symbol: str
    direction: Direction
    confidence: float
    reason_codes: list[str]


class Strategy(ABC):
    name: str

    @abstractmethod
    def generate_signal(self, symbol: str, candles: pd.DataFrame) -> Signal: ...
