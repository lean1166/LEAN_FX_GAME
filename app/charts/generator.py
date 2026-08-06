"""
Generador de velas para LEAN FX LIVE.

Genera un mercado continuo con:
- Tendencias largas
- Pullbacks naturales
- Volatilidad variable
- Sin límites artificiales de precio
"""

import random
from typing import Dict, List


class MarketState:
    def __init__(self):
        self.direction = random.choice([-1, 1])
        self.remaining = random.randint(18, 45)
        self.volatility = random.uniform(4, 9)

    def update(self):

        self.remaining -= 1

        if self.remaining <= 0:

            self.direction *= -1

            self.remaining = random.randint(18, 45)

            self.volatility = random.uniform(4, 9)


_state = MarketState()


def generate_candles(
    count: int,
    base_price: float = 1000.0
) -> List[Dict[str, float]]:

    candles = []

    price = base_price

    for _ in range(count):

        _state.update()

        # 80% sigue tendencia
        # 20% hace pequeño pullback

        if random.random() < 0.80:
            body = random.uniform(
                _state.volatility * 0.5,
                _state.volatility * 1.5,
            ) * _state.direction
        else:
            body = random.uniform(
                1,
                _state.volatility * 0.7,
            ) * -_state.direction

        open_price = price

        close_price = open_price + body

        upper_wick = random.uniform(0.5, _state.volatility)

        lower_wick = random.uniform(0.5, _state.volatility)

        high = max(open_price, close_price) + upper_wick

        low = min(open_price, close_price) - lower_wick

        candles.append(
            {
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close_price, 2),
            }
        )

        price = close_price

    return candles