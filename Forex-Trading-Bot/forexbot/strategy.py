"""Moving-average crossover strategy with ATR-based stops."""
from dataclasses import dataclass

import pandas as pd

from .indicators import atr, ema, sma


@dataclass(frozen=True)
class MACrossover:
    # Defaults are the best in-sample (2005-2018) result of `python bot.py optimize`.
    fast: int = 10
    slow: int = 100
    ma_type: str = "ema"      # "ema" or "sma"
    atr_period: int = 14
    stop_atr: float = 3.0     # stop-loss distance in ATRs
    target_atr: float = 0.0   # take-profit distance in ATRs (0 disables it)
    trailing: bool = True     # ratchet the stop to stop_atr ATRs behind each close

    def __post_init__(self):
        if self.fast >= self.slow:
            raise ValueError("fast period must be shorter than slow period")
        if self.ma_type not in ("ema", "sma"):
            raise ValueError("ma_type must be 'ema' or 'sma'")

    def indicators(self, bars: pd.DataFrame) -> pd.DataFrame:
        ma = ema if self.ma_type == "ema" else sma
        out = pd.DataFrame(index=bars.index)
        out["fast_ma"] = ma(bars["close"], self.fast)
        out["slow_ma"] = ma(bars["close"], self.slow)
        out["atr"] = atr(bars["high"], bars["low"], bars["close"], self.atr_period)
        # +1 while the fast MA is above the slow MA, -1 below, 0 during warm-up.
        # An exact tie keeps the previous side so it never hides a crossover.
        gap = out["fast_ma"] - out["slow_ma"]
        trend = (gap > 0).astype(int) - (gap < 0).astype(int)
        trend = trend.where(trend != 0).ffill().fillna(0).astype(int)
        out["trend"] = trend.where(out["slow_ma"].notna(), 0)
        # A signal fires only on the bar where the trend flips.
        flipped = out["trend"].ne(out["trend"].shift(1)) & out["trend"].ne(0) & out["trend"].shift(1).ne(0)
        out["signal"] = out["trend"].where(flipped, 0)
        return out
