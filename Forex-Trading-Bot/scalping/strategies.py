"""Seven classic EUR/USD scalping and intraday setups.

Each builder takes 1-minute bars plus parameters and returns a `Setup`
for the simulator. Everything is computed from data available at the close
of the signal bar; the simulator fills at the next bar's open.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data_m1 import PIP


@dataclass
class Setup:
    bars: pd.DataFrame
    signal: np.ndarray
    stop: np.ndarray
    target: np.ndarray
    flat: np.ndarray
    max_hold: int = 10_000


# ---------- helpers ----------

def resample(bars: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if minutes == 1:
        return bars
    rule = f"{minutes}min"
    out = bars.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "london_min": "first", "ny_min": "first", "day": "first"}).dropna()
    out["london_min"] = out["london_min"].astype(np.int16)
    out["ny_min"] = out["ny_min"].astype(np.int16)
    return out


def atr(bars: pd.DataFrame, n: int) -> pd.Series:
    prev = bars.close.shift(1)
    tr = pd.concat([bars.high - bars.low, (bars.high - prev).abs(), (bars.low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / down.replace(0, np.nan))


def between(minutes: pd.Series, start_hhmm: str, end_hhmm: str) -> np.ndarray:
    """True when a clock column (minutes after midnight) is inside [start, end)."""
    s = int(start_hhmm[:2]) * 60 + int(start_hhmm[3:])
    e = int(end_hhmm[:2]) * 60 + int(end_hhmm[3:])
    m = minutes.to_numpy()
    return (m >= s) & (m < e) if s < e else (m >= s) | (m < e)


def first_per_day(bars: pd.DataFrame, mask: np.ndarray) -> np.ndarray:
    """Keep only the first True of each trading day."""
    s = pd.Series(mask, index=bars.index)
    return (s & (s.groupby(bars["day"].to_numpy()).cumsum() == 1)).to_numpy()


def _setup(bars, long, short, stop, target, flat, max_hold=10_000) -> Setup:
    signal = np.where(long, 1, np.where(short, -1, 0)).astype(np.int8)
    return Setup(bars, signal, np.asarray(stop, float), np.asarray(target, float), np.asarray(flat), max_hold)


# ---------- 1. Asian-session Bollinger fade ----------

def asian_bollinger_fade(m1, tf=5, n=20, k=2.0, stop_pips=8.0):
    """Fade 2-sigma stretches while Tokyo trades and London sleeps, target the mid band."""
    b = resample(m1, tf)
    mid = b.close.rolling(n).mean()
    sd = b.close.rolling(n).std()
    active = between(b.london_min, "00:00", "06:00")
    long = active & (b.close < mid - k * sd).to_numpy()
    short = active & (b.close > mid + k * sd).to_numpy()
    target = (mid - b.close).abs().clip(lower=PIP).to_numpy()
    flat = ~between(b.london_min, "00:00", "07:00")
    return _setup(b, long, short, np.full(len(b), stop_pips * PIP), target, flat)


# ---------- 2. London open breakout of the Asian range ----------

def london_breakout(m1, buffer_pips=1.0, tp_mult=1.0, min_range=10, max_range=40):
    """Trade the first break of the 00:00-07:00 London range, stop at the far side."""
    b = m1
    asia = between(b.london_min, "00:00", "07:00")
    day = b["day"].to_numpy()
    hi = pd.Series(np.where(asia, b.high, np.nan), index=b.index).groupby(day).cummax()
    lo = pd.Series(np.where(asia, b.low, np.nan), index=b.index).groupby(day).cummin()
    hi, lo = hi.groupby(day).ffill(), lo.groupby(day).ffill()
    width = (hi - lo) / PIP
    window = between(b.london_min, "07:00", "10:00") & width.between(min_range, max_range).to_numpy()
    up = window & (b.close > hi + buffer_pips * PIP).to_numpy()
    down = window & (b.close < lo - buffer_pips * PIP).to_numpy()
    first = first_per_day(b, up | down)
    stop = (hi - lo + 2 * buffer_pips * PIP).to_numpy()
    flat = ~between(b.london_min, "00:00", "16:00")
    return _setup(b, first & up, first & down, stop, tp_mult * stop, flat)


# ---------- 3. RSI(2) pullback in the trend ----------

def rsi2_pullback(m1, tf=5, trend=200, lo=10, sl_atr=2.0, tp_atr=1.0, hold=24):
    """Buy short, sharp dips in an uptrend (and sell rips in a downtrend)."""
    b = resample(m1, tf)
    r = rsi(b.close, 2)
    ema = b.close.ewm(span=trend, adjust=False).mean()
    a = atr(b, 14)
    active = between(b.london_min, "07:00", "17:00")
    long = active & ((b.close > ema) & (r < lo)).to_numpy()
    short = active & ((b.close < ema) & (r > 100 - lo)).to_numpy()
    flat = ~between(b.london_min, "07:00", "18:00")
    return _setup(b, long, short, sl_atr * a, tp_atr * a, flat, hold)


# ---------- 4 & 5. One-minute impulse: follow it or fade it ----------

def _impulse(m1, k, sl_atr, tp_atr, hold, follow):
    b = m1
    a = atr(b, 60)
    body = b.close - b.open
    big = (body.abs() > k * a).to_numpy() & between(b.london_min, "07:00", "17:00")
    up, down = big & (body > 0).to_numpy(), big & (body < 0).to_numpy()
    long, short = (up, down) if follow else (down, up)
    flat = ~between(b.london_min, "07:00", "18:00")
    return _setup(b, long, short, sl_atr * a, tp_atr * a, flat, hold)


def impulse_momentum(m1, k=3.0, sl_atr=2.0, tp_atr=3.0, hold=15):
    """A 1-minute candle k times bigger than normal: jump on in its direction."""
    return _impulse(m1, k, sl_atr, tp_atr, hold, follow=True)


def impulse_fade(m1, k=3.0, sl_atr=3.0, tp_atr=1.5, hold=15):
    """The same oversized candle, traded as an overreaction that snaps back."""
    return _impulse(m1, k, sl_atr, tp_atr, hold, follow=False)


# ---------- 6. New York opening-range breakout ----------

def ny_range_breakout(m1, range_end="08:30", tp_mult=1.5, max_range=25):
    """Range from 08:00 New York to `range_end`, trade the first break before 11:00."""
    b = m1
    rng = between(b.ny_min, "08:00", range_end)
    day = b["day"].to_numpy()
    hi = pd.Series(np.where(rng, b.high, np.nan), index=b.index).groupby(day).cummax().groupby(day).ffill()
    lo = pd.Series(np.where(rng, b.low, np.nan), index=b.index).groupby(day).cummin().groupby(day).ffill()
    width = (hi - lo) / PIP
    window = between(b.ny_min, range_end, "11:00") & width.between(3, max_range).to_numpy()
    up, down = window & (b.close > hi).to_numpy(), window & (b.close < lo).to_numpy()
    first = first_per_day(b, up | down)
    stop = (hi - lo).to_numpy()
    flat = ~between(b.ny_min, "03:00", "12:00")
    return _setup(b, first & up, first & down, stop, tp_mult * stop, flat)


# ---------- 7. EMA trend pullback ----------

def ema_pullback(m1, tf=1, fast=20, slow=50, tp_r=1.5, swing=5):
    """In a stacked-EMA trend, buy the bar that dips to the fast EMA and closes back above it."""
    b = resample(m1, tf)
    ef = b.close.ewm(span=fast, adjust=False).mean()
    es = b.close.ewm(span=slow, adjust=False).mean()
    e200 = b.close.ewm(span=200, adjust=False).mean()
    active = between(b.london_min, "07:00", "17:00")
    up_trend = (ef > es) & (es > e200)
    dn_trend = (ef < es) & (es < e200)
    long = active & (up_trend & (b.low <= ef) & (b.close > ef) & (b.close > b.open)).to_numpy()
    short = active & (dn_trend & (b.high >= ef) & (b.close < ef) & (b.close < b.open)).to_numpy()
    swing_lo = b.low.rolling(swing).min()
    swing_hi = b.high.rolling(swing).max()
    stop = np.where(long, b.close - swing_lo, swing_hi - b.close) + 0.5 * PIP
    stop = np.maximum(stop, 2 * PIP)
    flat = ~between(b.london_min, "07:00", "18:00")
    return _setup(b, long, short, stop, tp_r * stop, flat)


# ---------- 8. London 4pm fix reversal ----------

def london_fix_reversal(m1, lookback="15:30", min_move=5.0, stop_mult=1.0, tp_mult=0.5, exit_at="17:00"):
    """Fade the run-up into the 16:00 London WM/Reuters benchmark fix.

    Fixing flows from asset managers push price into 16:00; once the window
    closes the pressure is gone and part of the move tends to give back.
    """
    b = m1
    day = b["day"].to_numpy()
    start = pd.Series(np.where(between(b.london_min, lookback, f"{lookback[:3]}{int(lookback[3:]) + 1:02d}"),
                               b.open, np.nan), index=b.index).groupby(day).ffill()
    move = (b.close - start) / PIP
    at_fix = between(b.london_min, "16:00", "16:01")
    long = at_fix & (move < -min_move).to_numpy()
    short = at_fix & (move > min_move).to_numpy()
    stop = stop_mult * move.abs().to_numpy() * PIP
    flat = ~between(b.london_min, "15:00", exit_at)
    return _setup(b, long, short, stop, tp_mult * stop, flat)


STRATEGIES = {
    "Asian Bollinger fade": asian_bollinger_fade,
    "London breakout": london_breakout,
    "RSI(2) trend pullback": rsi2_pullback,
    "1-min impulse momentum": impulse_momentum,
    "1-min impulse fade": impulse_fade,
    "NY opening-range breakout": ny_range_breakout,
    "EMA trend pullback": ema_pullback,
    "London 4pm fix reversal": london_fix_reversal,
}
