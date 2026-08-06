"""Japanese candlestick data model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    """Single OHLC candlestick."""

    open: float
    high: float
    low: float
    close: float

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    @property
    def body_top(self) -> float:
        return max(self.open, self.close)

    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)
