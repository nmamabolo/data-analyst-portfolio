"""Bar-by-bar backtest engine for a single currency pair.

Timing rules (no look-ahead):
  * Signals and ATR are computed on the close of bar t.
  * Orders fill at the open of bar t+1.
  * Stops and targets are checked against each bar's high/low. If a bar
    touches both, the stop is assumed to hit first. A gap through a level
    fills at the open, not at the level.
  * Half the spread is paid on entry and half on exit.

Positions are sized so that hitting the stop loses `risk_pct` of equity,
capped by `max_leverage`, and rounded down to micro lots (1,000 units).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import PairSpec
from .strategy import MACrossover

LOT_STEP = 1_000


@dataclass(frozen=True)
class RiskSettings:
    initial_equity: float = 10_000.0
    risk_pct: float = 0.01
    max_leverage: float = 10.0


@dataclass
class Position:
    direction: int
    units: float
    entry_date: pd.Timestamp
    entry_price: float
    stop: float
    target: float | None
    risk_usd: float


@dataclass
class BacktestResult:
    pair: str
    equity: pd.Series
    trades: pd.DataFrame
    indicators: pd.DataFrame
    open_position: Position | None = field(default=None)


def quote_to_usd(spec: PairSpec, price: float) -> float:
    """USD value of one unit of the pair's quote currency."""
    if spec.quote == "USD":
        return 1.0
    if spec.base == "USD":
        return 1.0 / price
    raise ValueError(f"{spec.symbol}: cross pairs need a conversion rate and are not supported")


def run_backtest(bars: pd.DataFrame, spec: PairSpec, strategy: MACrossover,
                 risk: RiskSettings = RiskSettings(), start=None, end=None) -> BacktestResult:
    """Trade between `start` and `end` (inclusive dates).

    Indicators warm up on all history before `start`, so the first trading
    day already has valid moving averages. Bars after `end` are never seen.
    """
    if end is not None:
        bars = bars.loc[:end]
    ind = strategy.indicators(bars)
    if start is not None:
        bars, ind = bars.loc[start:], ind.loc[start:]
    half_spread = spec.spread_pips * spec.pip / 2

    o, h, l, c = (bars[k].to_numpy() for k in ("open", "high", "low", "close"))
    signal = ind["signal"].to_numpy()
    atr_values = ind["atr"].to_numpy()
    dates = bars.index

    cash = risk.initial_equity
    pos: Position | None = None
    trades: list[dict] = []
    equity = np.empty(len(bars))

    def close_position(i: int, raw_price: float, reason: str) -> None:
        nonlocal cash, pos
        fill = raw_price - pos.direction * half_spread
        pnl = pos.direction * pos.units * (fill - pos.entry_price) * quote_to_usd(spec, fill)
        cash += pnl
        trades.append({
            "pair": spec.symbol,
            "direction": "long" if pos.direction > 0 else "short",
            "entry_date": pos.entry_date, "entry_price": pos.entry_price,
            "exit_date": dates[i], "exit_price": fill,
            "units": pos.units, "stop": pos.stop, "target": pos.target,
            "pnl_usd": pnl, "r_multiple": pnl / pos.risk_usd,
            "bars_held": i - dates.get_loc(pos.entry_date), "exit_reason": reason,
        })
        pos = None

    for i in range(len(bars)):
        pending = signal[i - 1] if i > 0 else 0

        # 1. At the open: act on yesterday's signal, or on a gap through a level.
        if pos is not None:
            d = pos.direction
            if pending == -d:
                close_position(i, o[i], "reverse")
            elif d * (o[i] - pos.stop) <= 0:
                close_position(i, o[i], "stop")
            elif pos.target is not None and d * (o[i] - pos.target) >= 0:
                close_position(i, o[i], "target")

        if pos is None and pending != 0 and not np.isnan(atr_values[i - 1]):
            d = int(pending)
            entry = o[i] + d * half_spread
            stop_dist = strategy.stop_atr * atr_values[i - 1]
            risk_usd = cash * risk.risk_pct
            units = risk_usd / (stop_dist * quote_to_usd(spec, entry))
            max_units = risk.max_leverage * cash / (entry * quote_to_usd(spec, entry))
            units = np.floor(min(units, max_units) / LOT_STEP) * LOT_STEP
            if units > 0:
                target = entry + d * strategy.target_atr * atr_values[i - 1] if strategy.target_atr else None
                pos = Position(d, units, dates[i], entry, entry - d * stop_dist, target,
                               units * stop_dist * quote_to_usd(spec, entry))

        # 2. During the bar: stop first, then target.
        if pos is not None:
            d = pos.direction
            worst, best = (l[i], h[i]) if d > 0 else (h[i], l[i])
            if d * (worst - pos.stop) <= 0:
                close_position(i, pos.stop, "stop")
            elif pos.target is not None and d * (best - pos.target) >= 0:
                close_position(i, pos.target, "target")

        # 3. At the close: trail the stop (it only ever tightens), then mark to market.
        open_pnl = 0.0
        if pos is not None:
            if strategy.trailing and not np.isnan(atr_values[i]):
                trail = c[i] - pos.direction * strategy.stop_atr * atr_values[i]
                pos.stop = max(pos.stop, trail) if pos.direction > 0 else min(pos.stop, trail)
            open_pnl = pos.direction * pos.units * (c[i] - pos.entry_price) * quote_to_usd(spec, c[i])
        equity[i] = cash + open_pnl

    return BacktestResult(
        pair=spec.symbol,
        equity=pd.Series(equity, index=dates, name=spec.symbol),
        trades=pd.DataFrame(trades),
        indicators=ind,
        open_position=pos,
    )
